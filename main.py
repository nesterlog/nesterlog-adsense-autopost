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
    """최근 발행 글의 제목·대표이미지 URL 수집."""
    titles = []
    image_urls = set()
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
            if title:
                titles.append(title)
            content = p.get("content") or ""
            for m in re.finditer(r'<img[^>]+src="(https://[^"]+)"', content, re.I):
                image_urls.add(m.group(1))
                break
    except Exception as e:
        print(f"최근 글 조회 실패(중복검사는 완화): {e}")
    return titles, image_urls


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


def generate_content(topic, category, recent_titles=None, exclude_image_urls=None):
    print(f"글 작성 중: {topic}")
    today = datetime.now().strftime("%Y년 %m월 %d일")
    recent_titles = recent_titles or []
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
(humanizer 원칙: AI티 제거 — '단순히~아니라', '핵심은 바로', '정리하자면' 남발 금지,
짧은 문장과 긴 문장을 섞고, 불필요한 강조·드라마틱 한 줄 마무리 금지)

블로그 니치: {BLOG_NICHE}
오늘 주제: "{topic}"
분류: {category}
작성일: {today}
{avoid_block}

문체:
- 존댓말, 자연스러운 구어체 약간 허용 ("저는 ~했어요", "이런 실수 했어요")
- 파워블로그처럼 허세·클릭베이트·이모지 과다 금지
- 구체적인 숫자/순서/실패 경험 최소 2개
- 독자가 오늘 바로 따라 할 수 있게

SEO / AEO(답변형) 요구:
- 제목·첫 문단에 핵심 검색어 자연스럽게
- H2/H3로 질문형·가이드형 소제목
- FAQ 3~4개 (사람들이 실제로 묻는 말투)
- 메타설명용 요약은 META_DESCRIPTION에만 (본문에 '메타:' 쓰지 말 것)
- GEO(지역 검색)는 주제가 지역과 관련될 때만 자연스럽게 (억지 지역명 남발 금지)

서식(HTML) — Blogger 에디터처럼 보이도록 적당히 꾸미기:
- 핵심 구절은 <strong>강조</strong> (과하면 안 됨, 글당 5~12회)
- 중요 팁 한 줄은 <blockquote><p>…</p></blockquote> 인용구 1~2개
- 비교·체크는 <table border="1" cellpadding="8"><tr><th>…</th></tr><tr><td>…</td></tr></table> 표 0~1개
- 목록은 <ul><li> 또는 <ol><li>
- 필요 시 <em>기울임</em>
- 글씨색·형광펜·밑줄(<u>)·과도한 스타일 금지 (저품질·광고처럼 보임)
- style= 인라인 색상 금지

중요 규칙:
1. 한국어 HTML만 (마크다운 금지)
2. 허위·의료/법률/투자 확정 조언 금지
3. 약 1,500~2,500자
4. 가짜 URL / href="#" 금지
5. 본문에 <img> 넣지 말 것
6. 본문에 "카테고리:" 문구 넣지 말 것
7. 애드센스·수익화 메타 주제 금지

응답 형식(이 순서를 반드시 지킬 것):

META_DESCRIPTION: [한글 70~90자, 검색 요약]
URL_SLUG: [영문-소문자-하이픈-슬러그]
PRIMARY_KEYWORDS: 키워드1, 키워드2, 키워드3
FOCUS_KEYPHRASE: [핵심 검색어 2~4단어]
IMAGE_ALT: [대표 이미지용 한글 설명 한 줄]

<article>
<h1>[검색의도 반영 제목, 자극적이지 않게]</h1>

<section class="introduction">
<p>[첫 문단에 핵심 키워드. 독자 고민으로 시작]</p>
<p>[이 글에서 얻을 것 한 줄]</p>
</section>

<section>
<h2>[소제목 1]</h2>
<p>[구체적 설명]</p>
<ul>
<li>[실천 팁]</li>
<li>[실천 팁]</li>
<li>[실천 팁]</li>
</ul>
</section>

<section>
<h2>[소제목 2]</h2>
<p>[추가 설명과 주의점]</p>
</section>

<section>
<h2>[소제목 3]</h2>
<p>[비교, 체크리스트, 또는 상황별 추천]</p>
</section>

<section class="faq">
<h2>자주 묻는 질문</h2>
<div itemscope itemtype="https://schema.org/FAQPage">
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">Q. [질문]?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<p itemprop="text">[답변]</p>
</div>
</div>
<!-- 질문을 3~4개 더 -->
</div>
</section>

<section class="conclusion">
<h2>정리</h2>
<p>[핵심 요약]</p>
<p><strong>비슷한 고민이 있다면 댓글로 남겨 주세요.</strong></p>
</section>
</article>
"""

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
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

            seo_data = {}
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
            except Exception as e:
                print(f"파싱 오류: {e}")
                title = topic
                body = content
                seo_data = {}

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
    year = datetime.now().strftime("%Y")

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
    note = ""
    if meta or slug or kw or focus:
        note = (
            f"<!-- ADSENSE_REVIEW_NOTE meta: {meta} | slug: {slug} | "
            f"focus: {focus} | keywords: {kw} | draft={POST_AS_DRAFT} -->\n"
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
        recent_titles, recent_images = get_recent_post_meta(svc, blog_id)
    except Exception as e:
        print(f"최근 글 메타 로드 실패: {e}")
        recent_titles, recent_images = [], set()
    print(f"최근 글 {len(recent_titles)}개, 사용 중 이미지 {len(recent_images)}개 제외")

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
