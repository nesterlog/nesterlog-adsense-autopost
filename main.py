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

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# 애드센스 승인용: 기본은 초안 저장 (true/false)
POST_AS_DRAFT = os.getenv("POST_AS_DRAFT", "true").lower() in ("1", "true", "yes")

# 블로그 한 줄 니치 (예: 생활정보, 육아, 재테크, 여행)
BLOG_NICHE = os.getenv("BLOG_NICHE", "생활정보와 실용 가이드")

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


def pick_topic():
    file_topics = load_topics_from_file()

    if TOPIC_SOURCE == "topics" and file_topics:
        topic = random.choice(file_topics)
        return topic, "주제목록"

    if TOPIC_SOURCE == "news":
        return get_korean_news_topic()

    # mixed (기본): 70% 주제목록, 30% 뉴스
    if file_topics and random.random() < 0.7:
        return random.choice(file_topics), "주제목록"

    news_topic, news_cat = get_korean_news_topic()
    if news_topic:
        return news_topic, news_cat

    if file_topics:
        return random.choice(file_topics), "주제목록"

    return None, None


def convert_markdown_to_html(text):
    """남은 마크다운만 최소 변환 (이미 HTML이면 대부분 그대로)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def build_featured_image_html(alt_text, english_keyword="lifestyle"):
    """대표 이미지 1장 HTML (테마 썸네일용). 무료 스톡 이미지."""
    safe_kw = re.sub(r"[^a-zA-Z0-9,\-]", "", english_keyword.replace(" ", ","))[:40] or "lifestyle"
    # picsum + 시드로 글마다 다른 이미지, 실패 시 unsplash 소스 대체 가능
    seed = abs(hash(alt_text)) % 100000
    src = f"https://picsum.photos/seed/{seed}/1200/630"
    alt = (alt_text or "대표 이미지").replace('"', "")
    return (
        f'<figure class="featured-image" style="margin:0 0 1.5em 0;">'
        f'<img src="{src}" alt="{alt}" width="1200" height="630" '
        f'style="max-width:100%;height:auto;border-radius:8px;" />'
        f"<figcaption style=\"font-size:0.9em;color:#666;\">{alt}</figcaption>"
        f"</figure>"
    )


def insert_featured_image(body, seo_data, topic):
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

    alt = seo_data.get("focus_keyphrase") or topic or BLOG_NICHE
    # 영문 키워드는 슬러그에서 추출
    en = seo_data.get("url_slug") or "daily,life,guide"
    en = en.replace("-", ",")
    img = build_featured_image_html(alt, en)

    if re.search(r"<img\s", body, re.IGNORECASE):
        return body

    if "</h1>" in body:
        return body.replace("</h1>", "</h1>\n" + img, 1)
    if "<article>" in body:
        return body.replace("<article>", "<article>\n" + img, 1)
    return img + "\n" + body


def generate_content(topic, category):
    print(f"글 작성 중: {topic}")
    today = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = f"""
당신은 한국 블로그 '네스터로그(nesterlog.com)'의 전문 한국어 블로거입니다.
애드센스 승인을 목표로, 독자에게 실제로 도움이 되는 고품질 한국어 글을 작성하세요.
직접 해본 것처럼 구체적인 숫자·순서·실패 사례를 넣고, 뻔한 AI 문장 투를 피하세요.

블로그 니치(주제 축): {BLOG_NICHE}
오늘 다룰 소재: "{topic}"
소재 출처 분류: {category}
작성일: {today}

중요 규칙:
1. 반드시 자연스러운 한국어로만 작성
2. 뉴스 베끼지 말고, 독자가 바로 따라 할 수 있는 가이드/체크리스트 중심
3. 허위·과장·의료/법률/투자 확정 조언 금지. 필요하면 "참고용"
4. HTML만 사용. 마크다운(**볼드**) 금지
5. 본문 한국어 기준 약 1,500~2,500자 분량
6. 존재하지 않는 URL 금지. 불확실하면 외부 링크 넣지 말 것
7. href="#" 금지
8. 본문에 <img> 태그 넣지 말 것 (이미지는 시스템이 따로 넣음)
9. "카테고리:" 라는 문구를 본문에 쓰지 말 것 (라벨은 시스템이 처리)
10. 제목/본문에 '애드센스 승인', '수익화 꿀팁' 같은 메타성 주제 금지

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

IMAGE_SUGGESTIONS:
1. Alt: "[한글 설명]" | Caption: "[캡션]"
2. Alt: "[한글 설명]" | Caption: "[캡션]"
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


def post_to_blogger(title, content, category, seo_data=None):
    if not title or not content:
        print("콘텐츠 생성 실패. 게시 생략.")
        return False

    if seo_data is None:
        seo_data = {}

    service = get_blogger_service()
    blog_id = os.environ["BLOGGER_BLOG_ID"]
    year = datetime.now().strftime("%Y")

    # 라벨(=Blogger 카테고리)은 3~5개만 — 키워드 나열은 저품질로 보임
    labels = [BLOG_NICHE]
    if seo_data.get("focus_keyphrase"):
        labels.append(seo_data["focus_keyphrase"])
    if seo_data.get("keywords"):
        labels.extend([kw.strip() for kw in seo_data["keywords"].split(",")[:2] if kw.strip()])
    labels = list(dict.fromkeys([x for x in labels if x]))[:5]

    seo_title = title
    if seo_data.get("focus_keyphrase") and seo_data["focus_keyphrase"].lower() not in title.lower():
        # 제목이 너무 길어지지 않게 보조 키워드는 라벨에만 두고 제목은 유지
        seo_title = title

    # 메타 설명을 HTML 주석으로 본문 상단에 남겨 검수 시 참고 (Blogger 커스텀 메타 제한 보완)
    meta = seo_data.get("meta_description", "")
    slug = seo_data.get("url_slug", "")
    note = ""
    if meta or slug:
        note = (
            f"<!-- ADSENSE_REVIEW_NOTE meta: {meta} | slug: {slug} | "
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
        print("다음 단계: Blogger에서 초안을 열어 이미지·문장 다듬은 뒤 발행하세요.")
        return True
    except Exception as e:
        print(f"Blogger 게시 오류: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("네스터로그 애드센스용 자동 초안 생성기")
    print(f"니치: {BLOG_NICHE}")
    print(f"초안 모드: {POST_AS_DRAFT}")
    print(f"주제 소스: {TOPIC_SOURCE}")
    print("=" * 60)

    max_topic_attempts = 5
    for attempt in range(max_topic_attempts):
        print(f"\n시도 {attempt + 1}/{max_topic_attempts}\n")
        topic, category = pick_topic()
        if not topic:
            print("주제를 찾지 못했습니다. 재시도...")
            time.sleep(3)
            continue

        title, body, cat, seo_data = generate_content(topic, category)
        if title and body:
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
