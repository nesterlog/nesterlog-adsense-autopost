import os
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from image_pool import featured_image_html

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# A모드(쉬운 모드): 기본 자동 공개. 초안만 원하면 POST_AS_DRAFT=true
POST_AS_DRAFT = os.getenv("POST_AS_DRAFT", "false").lower() in ("1", "true", "yes")

# 블로그 한 줄 니치 (글 톤/프롬프트용)
BLOG_NICHE = os.getenv("BLOG_NICHE", "생활정보와 실용 가이드")

# 메뉴·카테고리와 동일한 필수 라벨 (Blogger에서 라벨=카테고리)
# 상단 메뉴 '생활꿀팁'과 반드시 일치해야 분류에 표시됨
PRIMARY_LABEL = os.getenv("PRIMARY_LABEL", "생활꿀팁")

# 주제 선택: topics = topics_ko.txt / news = 한국 뉴스 / mixed = 둘 다
TOPIC_SOURCE = os.getenv("TOPIC_SOURCE", "topics").lower()

TOPICS_FILE = Path(__file__).resolve().parent / "topics_ko.txt"


def get_blogger_service():
    creds = Credentials(
        None,
        refresh_token=os.environ["G_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["G_CLIENT_ID"],
        client_secret=os.environ["G_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    return build("blogger", "v3", credentials=creds)


def load_topics_from_file():
    if not TOPICS_FILE.exists():
        return []
    lines = []
    for line in TOPICS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


_STOPWORDS = {
    "방법",
    "하는",
    "위한",
    "간단한",
    "정리",
    "팁",
    "가이드",
    "현실적인",
    "따라",
    "하는",
    "초보도",
    "초보",
    "관련",
    "대한",
    "있는",
    "없는",
    "그리고",
    "또는",
    "생활",
    "요령",
    "실천",
    "계절별",
    "겪어보고",
    "정착한",
}


def _norm_text(s: str) -> str:
    return re.sub(r"[\s,.\-_/·|]+", "", (s or "").lower())


def _tokens(s: str) -> set:
    toks = re.findall(r"[가-힣a-zA-Z0-9]{2,}", s or "")
    return {t.lower() for t in toks if t.lower() not in _STOPWORDS}


def is_similar_topic(a: str, b: str, threshold: float = 0.45) -> bool:
    """제목/주제가 너무 비슷하면 True (중복 발행 방지)."""
    if not a or not b:
        return False
    na, nb = _norm_text(a), _norm_text(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= threshold


def get_recent_post_meta(service, blog_id, max_results=40):
    """최근 발행 글의 제목·URL·대표이미지·발행시각 수집."""
    titles = []
    image_urls = set()
    posts_meta = []
    try:
        items = (
            service.posts()
            .list(
                blogId=blog_id,
                fetchBodies=True,
                maxResults=max_results,
                status="LIVE",
            )
            .execute()
            .get("items")
            or []
        )
        for p in items:
            title = (p.get("title") or "").strip()
            url = (p.get("url") or "").strip()
            published = p.get("published") or ""
            if title:
                titles.append(title)
            if title and url:
                posts_meta.append(
                    {"title": title, "url": url, "published": published}
                )
            content = p.get("content") or ""
            for m in re.finditer(r'<img[^>]+src="(https://[^"]+)"', content, re.I):
                image_urls.add(m.group(1))
                break
    except Exception as e:
        print(f"최근 글 조회 실패(중복검사는 완화): {e}")
    return titles, image_urls, posts_meta


def hours_since_latest_post(posts_meta) -> float | None:
    """가장 최근 LIVE 글로부터 경과 시간(시간). 없으면 None."""
    if not posts_meta:
        return None
    raw = posts_meta[0].get("published") or ""
    if not raw:
        return None
    try:
        # 2026-10-23T01:17:00-07:00 형태
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return (now - dt).total_seconds() / 3600.0
    except Exception:
        return None


# GitHub cron 백업 슬롯이 겹쳐도 하루에 과다 발행되지 않게
MIN_HOURS_BETWEEN_POSTS = float(os.getenv("MIN_HOURS_BETWEEN_POSTS", "6"))


def strip_invisible_unicode(text: str) -> str:
    """보이지 않는 포맷 문자(제로폭 등) 제거 — 본문 위생용."""
    if not text:
        return text
    drop = {
        0x200B,
        0x200C,
        0x200D,
        0x2060,
        0xFEFF,
        0x00AD,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
    }
    return "".join(ch for ch in text if ord(ch) not in drop)


LAYOUT_TEMPLATES = {
    "guide": {
        "name": "실용 가이드형",
        "body": """
<article>
<h1>[검색의도 반영 제목]</h1>
<section class="introduction">
<p>[고민으로 시작, 핵심 키워드 자연스럽게]</p>
<p>[이 글에서 얻을 것 한 줄]</p>
</section>
<section>
<h2>[소제목 1 — 준비/기준]</h2>
<p>[설명]</p>
<ul><li>[팁]</li><li>[팁]</li><li>[팁]</li></ul>
</section>
<section>
<h2>[소제목 2 — 실천]</h2>
<p>[설명과 주의점]</p>
</section>
<section>
<h2>[소제목 3 — 상황별]</h2>
<p>[비교 또는 체크]</p>
</section>
<section class="faq">
<h2>자주 묻는 질문</h2>
<div itemscope itemtype="https://schema.org/FAQPage">
<!-- Question 블록 3~4개 (schema.org FAQ) -->
</div>
</section>
<section class="conclusion">
<h2>정리</h2>
<p>[요약]</p>
<p><strong>[자연스러운 마무리 한 줄 — 매 글마다 다른 표현]</strong></p>
</section>
</article>
""",
    },
    "checklist": {
        "name": "체크리스트형",
        "body": """
<article>
<h1>[검색의도 반영 제목]</h1>
<p>[짧은 도입 2~3문장. introduction 섹션 클래스 쓰지 말 것]</p>
<section>
<h2>바로 쓰는 체크리스트</h2>
<ol>
<li><strong>[항목]</strong> — [한 줄 설명]</li>
<li><strong>[항목]</strong> — [한 줄 설명]</li>
<li><strong>[항목]</strong> — [한 줄 설명]</li>
<li><strong>[항목]</strong> — [한 줄 설명]</li>
<li><strong>[항목]</strong> — [한 줄 설명]</li>
</ol>
</section>
<section>
<h2>놓치기 쉬운 포인트</h2>
<p>[실패 경험 1개 + 교정법]</p>
<blockquote><p>[기억할 한 줄]</p></blockquote>
</section>
<section>
<h2>궁금할 수 있는 점</h2>
<p><strong>Q.</strong> [질문]<br/>[답변 2~3문장]</p>
<p><strong>Q.</strong> [질문]<br/>[답변]</p>
<p><strong>Q.</strong> [질문]<br/>[답변]</p>
</section>
<p>[짧은 마무리. '정리'라는 단어 반복 금지]</p>
</article>
""",
    },
    "story": {
        "name": "실수담→해결형",
        "body": """
<article>
<h1>[검색의도 반영 제목]</h1>
<section>
<h2>이렇게 실패했어요</h2>
<p>[구체적 실패 장면, 숫자 포함]</p>
<p>[그때 든 생각]</p>
</section>
<section>
<h2>바꿔 보니 달라진 점</h2>
<p>[해결 과정 2단계 이상]</p>
<ul><li>[바뀐 습관]</li><li>[바뀐 습관]</li></ul>
</section>
<section>
<h2>지금 쓰는 기준</h2>
<table border="1" cellpadding="8">
<tr><th>상황</th><th>이렇게</th></tr>
<tr><td>[상황1]</td><td>[행동1]</td></tr>
<tr><td>[상황2]</td><td>[행동2]</td></tr>
<tr><td>[상황3]</td><td>[행동3]</td></tr>
</table>
</section>
<section class="faq">
<h2>자주 묻는 질문</h2>
<div itemscope itemtype="https://schema.org/FAQPage">
<!-- FAQ 2~3개만 -->
</div>
</section>
<p>[담백한 마무리 2문장]</p>
</article>
""",
    },
    "timeline": {
        "name": "하루 타임라인형",
        "body": """
<article>
<h1>[검색의도 반영 제목]</h1>
<p>[왜 루틴이 필요한지 짧은 도입]</p>
<section>
<h2>아침</h2>
<p>[행동 + 이유]</p>
<ul><li>[세부]</li><li>[세부]</li></ul>
</section>
<section>
<h2>낮·오후</h2>
<p>[행동 + 현실적인 타협]</p>
</section>
<section>
<h2>저녁·자기 전</h2>
<p>[행동 + 주의]</p>
<blockquote><p>[기억할 한 줄]</p></blockquote>
</section>
<section>
<h2>하루에 이 정도면 충분합니다</h2>
<p>[과하지 않게 요약. FAQ 섹션 넣지 말 것]</p>
<p><strong>Q.</strong> [예상 질문 1]<br/>[짧은 답]</p>
<p><strong>Q.</strong> [예상 질문 2]<br/>[짧은 답]</p>
</section>
</article>
""",
    },
    "compare": {
        "name": "비교·선택형",
        "body": """
<article>
<h1>[검색의도 반영 제목]</h1>
<section class="introduction">
<p>[선택지가 헷갈리는 상황으로 시작]</p>
</section>
<section>
<h2>한눈에 고르는 기준</h2>
<table border="1" cellpadding="8">
<tr><th>구분</th><th>이럴 때</th><th>비고</th></tr>
<tr><td>[A]</td><td>[조건]</td><td>[팁]</td></tr>
<tr><td>[B]</td><td>[조건]</td><td>[팁]</td></tr>
<tr><td>[C]</td><td>[조건]</td><td>[팁]</td></tr>
</table>
</section>
<section>
<h2>저는 이렇게 골랐어요</h2>
<p>[개인 기준 + 숫자/기간]</p>
<ol><li>[단계]</li><li>[단계]</li><li>[단계]</li></ol>
</section>
<section class="faq">
<h2>자주 묻는 질문</h2>
<div itemscope itemtype="https://schema.org/FAQPage">
<!-- FAQ 3개 -->
</div>
</section>
<section class="conclusion">
<h2>한 줄로 말하면</h2>
<p>[결론. 댓글 유도 문구는 매번 다른 표현]</p>
</section>
</article>
""",
    },
}


def pick_layout():
    key = random.choice(list(LAYOUT_TEMPLATES.keys()))
    layout = LAYOUT_TEMPLATES[key]
    print(f"레이아웃: {layout['name']} ({key})")
    return key, layout


def append_related_posts(body: str, posts_meta: list, limit: int = 2) -> str:
    """본문 끝에 기존 글 내부링크 1~2개 (체류·SEO)."""
    if not posts_meta or not body:
        return body
    picks = [p for p in posts_meta if p.get("url") and p.get("title")]
    if not picks:
        return body
    random.shuffle(picks)
    picks = picks[:limit]
    items = "".join(
        f'<li><a href="{p["url"]}">{p["title"]}</a></li>' for p in picks
    )
    block = (
        '<section class="related-posts" style="margin-top:2em;">'
        "<h2>같이 보면 좋은 글</h2>"
        f"<ul>{items}</ul>"
        "</section>"
    )
    if re.search(r"</article>", body, re.I):
        return re.sub(r"</article>", block + "\n</article>", body, count=1, flags=re.I)
    return body + "\n" + block


def conflicts_with_recent(candidate: str, recent_titles: list) -> str | None:
    for t in recent_titles:
        if is_similar_topic(candidate, t):
            return t
    return None


def get_korean_news_topic():
    rss_feeds = {
        "주요뉴스": "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
        "경제": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",
        "기술": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko",
        "생활": "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ko&gl=KR&ceid=KR:ko",
        "과학": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ko&gl=KR&ceid=KR:ko",
    }

    category_name, rss_url = random.choice(list(rss_feeds.items()))
    print(f"뉴스 카테고리 검색: {category_name}")

    try:
        response = requests.get(rss_url, timeout=30)
        if response.status_code != 200:
            print(f"RSS 오류: {response.status_code}")
            return None, None

        root = ET.fromstring(response.content)
        trends = []
        for item in root.findall(".//item")[:15]:
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue
            clean_title = title_el.text.split(" - ")[0].strip()
            if clean_title:
                trends.append(clean_title)

        if not trends:
            return None, None
        return random.choice(trends), category_name
    except Exception as e:
        print(f"뉴스 가져오기 실패: {e}")
        return None, None


def pick_topic(recent_titles=None):
    """최근 글과 겹치지 않는 주제 선택."""
    recent_titles = recent_titles or []
    file_topics = load_topics_from_file()

    def _ok(topic):
        hit = conflicts_with_recent(topic, recent_titles)
        if hit:
            print(f"중복 주제 스킵: '{topic}' ≈ '{hit}'")
            return False
        return True

    # 파일 주제: 미사용 후보 우선 셔플
    fresh_file = [t for t in file_topics if _ok(t)]
    random.shuffle(fresh_file)

    if TOPIC_SOURCE == "topics":
        if fresh_file:
            return fresh_file[0], "주제목록"
        if file_topics:
            print("경고: 미사용 주제가 거의 없음. 가장 덜 겹치는 후보 사용.")
            return random.choice(file_topics), "주제목록"
        return None, None

    if TOPIC_SOURCE == "news":
        for _ in range(8):
            topic, cat = get_korean_news_topic()
            if topic and _ok(topic):
                return topic, cat
        return get_korean_news_topic()

    # mixed: 70% 주제목록, 30% 뉴스 (중복 제외)
    if fresh_file and random.random() < 0.7:
        return fresh_file[0], "주제목록"

    for _ in range(6):
        news_topic, news_cat = get_korean_news_topic()
        if news_topic and _ok(news_topic):
            return news_topic, news_cat

    if fresh_file:
        return fresh_file[0], "주제목록"
    if file_topics:
        return random.choice(file_topics), "주제목록"
    return None, None


def convert_markdown_to_html(text):
    """남은 마크다운만 최소 변환 (이미 HTML이면 대부분 그대로)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def insert_featured_image(body, seo_data, topic, exclude_image_urls=None):
    """본문 맨 앞(또는 h1 뒤)에 대표 이미지 1장 삽입. 카테고리 메타 줄 제거."""
    body = re.sub(
        r'<p class="meta">.*?</p>',
        "",
        body,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    body = re.sub(r"<strong>카테고리:.*?</strong>\s*\|\s*", "", body)
    body = re.sub(r"카테고리:\s*[^|<]+(\||</)", r"\1", body)
    # 깨진 외부 이미지(loremflickr 등) 제거 후 재삽입
    body = re.sub(
        r'<figure class="featured-image">.*?</figure>',
        "",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    body = re.sub(
        r'<img[^>]+loremflickr[^>]+>',
        "",
        body,
        flags=re.IGNORECASE,
    )

    alt = (
        seo_data.get("image_alt")
        or seo_data.get("focus_keyphrase")
        or topic
        or BLOG_NICHE
    )
    slug = seo_data.get("url_slug") or ""
    img = featured_image_html(
        alt,
        topic=topic,
        slug=slug,
        exclude_urls=exclude_image_urls,
    )

    if re.search(r"<img\s", body, re.IGNORECASE):
        return body

    if "</h1>" in body:
        return body.replace("</h1>", "</h1>\n" + img, 1)
    if "<article>" in body:
        return body.replace("<article>", "<article>\n" + img, 1)
    return img + "\n" + body


def generate_content(
    topic,
    category,
    recent_titles=None,
    exclude_image_urls=None,
    recent_posts=None,
):
    print(f"글 작성 중: {topic}")
    today = datetime.now().strftime("%Y년 %m월 %d일")
    recent_titles = recent_titles or []
    recent_posts = recent_posts or []
    layout_key, layout = pick_layout()
    avoid_block = ""
    if recent_titles:
        sample = "\n".join(f"- {t}" for t in recent_titles[:20])
        avoid_block = f"""
이미 발행된 글(절대 비슷한 제목·같은 각도 금지):
{sample}
- 위 목록과 겹치는 키워드·상황을 피하고, 다른 생활 장면·다른 실천법을 다루세요.
- 제목도 위와 비슷하면 안 됩니다.
"""

    prompt = f"""
당신은 한국 생활정보 블로그 '네스터로그'를 쓰는 실제 사람입니다.
인플루언서 과장 톤이 아니라, 옆집 친구가 경험 공유하듯 담백하고 구체적으로 쓰세요.
(humanizer 원칙: AI티 제거 — '단순히~아니라', '핵심은 바로', '정리하자면',
'알아보겠습니다', '이번 글에서는', '도움이 되셨길' 남발 금지.
짧은 문장과 긴 문장을 섞고, 불필요한 강조·드라마틱 한 줄 마무리 금지)

블로그 니치: {BLOG_NICHE}
오늘 주제: "{topic}"
분류: {category}
작성일: {today}
오늘 레이아웃: {layout['name']} ({layout_key})
{avoid_block}

문체:
- 존댓말, 자연스러운 구어체 약간 허용 ("저는 ~했어요", "이런 실수 했어요")
- 파워블로그 허세·클릭베이트·이모지 과다 금지
- 구체적인 숫자/순서/실패 경험 최소 2개
- 독자가 오늘 바로 따라 할 수 있게
- 마무리 문장은 매 글마다 다른 표현 (같은 댓글 유도 문구 반복 금지)

SEO / AEO:
- 제목·첫 문단에 핵심 검색어 자연스럽게
- 소제목은 질문형·가이드형 섞기
- 레이아웃에 FAQ/스키마가 있으면 충실히, 없으면 억지로 넣지 말 것
- 메타설명은 META_DESCRIPTION에만
- GEO는 지역 관련 주제일 때만 자연스럽게

서식:
- <strong> 글당 4~10회, blockquote 0~2개
- 표는 레이아웃이 요구할 때만
- 색상·형광펜·밑줄·인라인 style 색상 금지

중요 규칙:
1. 한국어 HTML만 (마크다운 금지)
2. 허위·의료/법률/투자 확정 조언 금지
3. 약 1,500~2,600자
4. 가짜 URL / href="#" 금지
5. 본문에 <img> 넣지 말 것
6. "카테고리:" / 애드센스·수익화 메타 주제 금지
7. 아래 레이아웃 뼈대를 따르되, 대괄호 안은 모두 실제 내용으로 채울 것

응답 형식(순서 고정):

META_DESCRIPTION: [한글 70~90자]
URL_SLUG: [영문-소문자-하이픈]
PRIMARY_KEYWORDS: 키워드1, 키워드2, 키워드3
FOCUS_KEYPHRASE: [핵심 검색어 2~4단어]
IMAGE_ALT: [대표 이미지용 한글 한 줄]

{layout['body']}
"""

    max_retries = 3
    retry_delay = 2
    temperature = round(random.uniform(0.85, 1.05), 2)

    for attempt in range(max_retries):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "topP": 0.95,
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ],
            }

            response = requests.post(GEMINI_API_URL, json=payload, timeout=90)

            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)
                    print(f"요청 한도. {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                    continue
                print("재시도 후에도 한도 초과")
                return None, None, None, {}

            response.raise_for_status()
            result = response.json()

            if "candidates" not in result or not result["candidates"]:
                print(f"응답 없음: {result}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return None, None, None, {}

            candidate = result["candidates"][0]
            if "content" not in candidate:
                print(f"안전필터 등으로 차단: {candidate.get('finishReason')}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None, None, None, {}

            content = candidate["content"]["parts"][0]["text"]
            content = content.replace("```html", "").replace("```", "")
            content = convert_markdown_to_html(content)
            content = strip_invisible_unicode(content)

            seo_data = {"layout": layout_key}
            try:
                if "META_DESCRIPTION:" in content:
                    s = content.find("META_DESCRIPTION:") + len("META_DESCRIPTION:")
                    e = content.find("\n", s)
                    seo_data["meta_description"] = content[s:e].strip()

                if "URL_SLUG:" in content:
                    s = content.find("URL_SLUG:") + len("URL_SLUG:")
                    e = content.find("\n", s)
                    seo_data["url_slug"] = content[s:e].strip()

                if "PRIMARY_KEYWORDS:" in content:
                    s = content.find("PRIMARY_KEYWORDS:") + len("PRIMARY_KEYWORDS:")
                    e = content.find("\n", s)
                    seo_data["keywords"] = content[s:e].strip()

                if "FOCUS_KEYPHRASE:" in content:
                    s = content.find("FOCUS_KEYPHRASE:") + len("FOCUS_KEYPHRASE:")
                    e = content.find("\n", s)
                    seo_data["focus_keyphrase"] = content[s:e].strip()

                if "IMAGE_ALT:" in content:
                    s = content.find("IMAGE_ALT:") + len("IMAGE_ALT:")
                    e = content.find("\n", s)
                    seo_data["image_alt"] = content[s:e].strip()

                start = content.find("<h1>") + 4
                end = content.find("</h1>")
                title = content[start:end].strip() if start > 3 and end > start else topic

                article_start = content.find("<article>")
                if article_start == -1:
                    article_start = content.find("<h1>")
                article_end = content.find("IMAGE_SUGGESTIONS:")
                if article_end == -1:
                    article_end = len(content)
                body = content[article_start:article_end].strip()
                body = strip_invisible_unicode(body)
                body = insert_featured_image(
                    body,
                    {
                        **seo_data,
                        "focus_keyphrase": seo_data.get("image_alt")
                        or seo_data.get("focus_keyphrase"),
                    },
                    topic,
                    exclude_image_urls=exclude_image_urls,
                )
                body = append_related_posts(body, recent_posts, limit=2)
            except Exception as e:
                print(f"파싱 오류: {e}")
                title = topic
                body = content
                seo_data = {"layout": layout_key}

            return title, body, category, seo_data

        except requests.exceptions.HTTPError as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2**attempt)
                print(f"HTTP 오류. {wait_time}초 후 재시도...")
                time.sleep(wait_time)
                continue
            print(f"Gemini API 오류: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(e.response.text)
            return None, None, None, {}
        except Exception as e:
            print(f"예상치 못한 오류: {e}")
            return None, None, None, {}

    return None, None, None, {}


def build_labels(seo_data=None):
    """카테고리 라벨 생활꿀팁을 항상 첫 번째로 반환."""
    seo_data = seo_data or {}
    secondary = []
    if seo_data.get("focus_keyphrase"):
        secondary.append(seo_data["focus_keyphrase"].strip())
    if seo_data.get("keywords"):
        secondary.extend(
            [kw.strip() for kw in seo_data["keywords"].split(",")[:3] if kw.strip()]
        )

    cleaned = []
    for x in secondary:
        if not x:
            continue
        if x == BLOG_NICHE or x == "생활정보와 실용 가이드":
            continue
        if x == PRIMARY_LABEL:
            continue
        # 가나다순에서 PRIMARY보다 앞에 오면 홈 해시태그가 카테고리를 덮음 → 제외
        if x < PRIMARY_LABEL:
            print(f"보조 라벨 제외(정렬상 '{PRIMARY_LABEL}'보다 앞): {x}")
            continue
        if x not in cleaned:
            cleaned.append(x)

    labels = [PRIMARY_LABEL] + cleaned
    return labels[:4]


def post_to_blogger(title, content, category, seo_data=None):
    if not title or not content:
        print("콘텐츠 생성 실패. 게시 생략.")
        return False

    if seo_data is None:
        seo_data = {}

    service = get_blogger_service()
    blog_id = os.environ["BLOGGER_BLOG_ID"]

    # 라벨(=카테고리): PRIMARY_LABEL(생활꿀팁)은 항상 1번.
    # Blogger/테마가 라벨을 가나다순으로 보여 주므로,
    # 생활꿀팁보다 앞에 정렬되는 보조 라벨은 붙이지 않음(SEO는 메타 주석에 남김).
    labels = build_labels(seo_data)
    print(f"라벨 순서: {labels}")

    seo_title = title
    if seo_data.get("focus_keyphrase") and seo_data["focus_keyphrase"].lower() not in title.lower():
        # 제목이 너무 길어지지 않게 보조 키워드는 라벨에만 두고 제목은 유지
        seo_title = title

    # 메타 설명을 HTML 주석으로 본문 상단에 남겨 검수 시 참고 (Blogger 커스텀 메타 제한 보완)
    meta = seo_data.get("meta_description", "")
    slug = seo_data.get("url_slug", "")
    kw = seo_data.get("keywords", "")
    focus = seo_data.get("focus_keyphrase", "")
    layout = seo_data.get("layout", "")
    note = ""
    if meta or slug or kw or focus or layout:
        note = (
            f"<!-- ADSENSE_REVIEW_NOTE meta: {meta} | slug: {slug} | "
            f"focus: {focus} | keywords: {kw} | layout: {layout} | "
            f"draft={POST_AS_DRAFT} -->\n"
        )

    body = {
        "kind": "blogger#post",
        "title": seo_title[:100],
        "content": note + content,
        "labels": labels,
    }

    try:
        posts = service.posts()
        result = posts.insert(blogId=blog_id, body=body, isDraft=POST_AS_DRAFT).execute()
        mode = "초안 저장" if POST_AS_DRAFT else "공개 발행"
        url = result.get("url") or result.get("id")
        print(f"{mode} 완료: {url}")
        if seo_data:
            print("SEO 참고 정보:")
            if meta:
                print(f"  메타: {meta}")
            if seo_data.get("focus_keyphrase"):
                print(f"  핵심어: {seo_data['focus_keyphrase']}")
            if seo_data.get("keywords"):
                print(f"  키워드: {seo_data['keywords']}")
        if POST_AS_DRAFT:
            print("초안 모드: Blogger 초안함에서 확인하세요.")
        else:
            print("A모드: 자동 공개 완료. 사이트에서 확인하세요.")
        return True
    except Exception as e:
        print(f"Blogger 게시 오류: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("네스터로그 애드센스 자동 발행 (A모드 지원)")
    print(f"니치: {BLOG_NICHE}")
    print(f"초안만 저장: {POST_AS_DRAFT}")
    print(f"주제 소스: {TOPIC_SOURCE}")
    print("=" * 60)

    blog_id = os.environ.get("BLOGGER_BLOG_ID") or "1587705316274533593"
    try:
        svc = get_blogger_service()
        recent_titles, recent_images, recent_posts = get_recent_post_meta(svc, blog_id)
    except Exception as e:
        print(f"최근 글 메타 로드 실패: {e}")
        recent_titles, recent_images, recent_posts = [], set(), []
    print(f"최근 글 {len(recent_titles)}개, 사용 중 이미지 {len(recent_images)}개 제외")

    # 백업 cron이 연달아 돌아도 과다 발행 방지 (수동 Run은 항상 허용)
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    elapsed = hours_since_latest_post(recent_posts)
    if (
        event_name == "schedule"
        and elapsed is not None
        and elapsed < MIN_HOURS_BETWEEN_POSTS
    ):
        print(
            f"최근 글이 {elapsed:.1f}시간 전 발행됨 "
            f"(최소 간격 {MIN_HOURS_BETWEEN_POSTS}시간). 스케줄 백업 건너뜀."
        )
        raise SystemExit(0)

    max_topic_attempts = 8
    for attempt in range(max_topic_attempts):
        print(f"\n시도 {attempt + 1}/{max_topic_attempts}\n")
        topic, category = pick_topic(recent_titles)
        if not topic:
            print("주제를 찾지 못했습니다. 재시도...")
            time.sleep(3)
            continue

        title, body, cat, seo_data = generate_content(
            topic,
            category,
            recent_titles=recent_titles,
            exclude_image_urls=recent_images,
            recent_posts=recent_posts,
        )
        if title and body:
            hit = conflicts_with_recent(title, recent_titles)
            if hit:
                print(f"생성된 제목이 기존 글과 유사 → 재시도: '{title}' ≈ '{hit}'")
                time.sleep(2)
                continue
            ok = post_to_blogger(title, body, cat, seo_data)
            if ok:
                print("\n완료!")
                break
        else:
            print(f"생성 실패 주제: {topic}")
            if attempt < max_topic_attempts - 1:
                time.sleep(3)
            else:
                print("모든 시도 실패.")
                raise SystemExit(1)
    else:
        print("중복을 피한 발행에 실패했습니다.")
        raise SystemExit(1)
