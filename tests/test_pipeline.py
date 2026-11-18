"""발행 파이프라인 오프라인 점검 (네트워크·자격증명 없이 실행).

    python3 tests/test_pipeline.py

Gemini 응답과 Blogger 서비스를 가짜로 바꿔 끼워, 실제 발행 경로에서
본문·이미지·내부링크·메타 처리와 발행 전 검사가 의도대로 동작하는지 확인한다.
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("BLOGGER_BLOG_ID", "test-blog")

import image_pool  # noqa: E402
import main  # noqa: E402


# ---------------------------------------------------------------- 고정 응답
BODY_PARAGRAPHS = (
    "퇴사 뒤 국민연금공단 고지서를 받으면 소득이 끊긴 상태에서 매달 보험료가 "
    "부과됩니다. 국민연금법 제91조에 따른 납부예외를 신청하면 무소득 기간의 "
    "납부를 일시 중단할 수 있고, 연체금도 붙지 않습니다. "
) * 20

FAKE_LLM_TEXT = f"""
META_DESCRIPTION: 실직 후 국민연금 납부예외 신청 자격과 실업크레딧 75% 정부지원 신청 절차를 공단 전자민원 경로 기준으로 정리했습니다.
URL_SLUG: national-pension-payment-exception
PRIMARY_KEYWORDS: 국민연금 납부예외, 실업크레딧, 국민연금 실직
FOCUS_KEYPHRASE: 국민연금 납부예외 신청
IMAGE_ALT: 국민연금공단 전자민원에서 납부예외를 신청하는 서류 작업 화면

<article>
<h1>실직 후 국민연금 납부예외 신청 자격과 실업크레딧 75% 챙기기</h1>
<section class="introduction">
<p>{BODY_PARAGRAPHS}</p>
</section>
<section>
<h2>납부예외 신청 자격 기준</h2>
<p>근로소득과 사업소득이 모두 끊긴 상태여야 하며, 3.3% 원천징수 내역이 남아 있으면 취소될 수 있습니다.</p>
<ul><li>가입 기간 120개월 미산입</li><li>재취업 시 다음 달 15일까지 재개 신고</li></ul>
</section>
<section>
<h2>전자민원 3단계 절차</h2>
<table border="1"><tr><th>단계</th><th>경로</th></tr>
<tr><td>1</td><td>전자민원 &gt; 개인민원</td></tr>
<tr><td>2</td><td>가입자 자격신고</td></tr></table>
</section>
<section class="conclusion">
<h2>정리</h2>
<p>구직급여를 받고 있다면 실업크레딧을 먼저 확인하고, 수급이 끝났다면 납부예외를 신청하세요.</p>
</section>
</article>
"""


class FakeResponse:
    status_code = 200

    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


class FakeInsert:
    def __init__(self, sink):
        self.sink = sink

    def execute(self):
        return {"url": "https://www.nesterlog.com/2026/11/test.html"}


class FakePosts:
    def __init__(self, sink):
        self.sink = sink

    def insert(self, blogId=None, body=None, isDraft=False):
        self.sink.update(body or {})
        return FakeInsert(self.sink)


class FakeService:
    def __init__(self):
        self.sent = {}

    def posts(self):
        return FakePosts(self.sent)


def fake_post(url, json=None, timeout=None, **kwargs):
    return FakeResponse(FAKE_LLM_TEXT)


RECENT_POSTS = [
    {
        "title": "윈도우11 작업표시줄 멈춤 현상 작업관리자 강제 재시작 가이드",
        "url": "https://www.nesterlog.com/2026/11/11.html",
        "published": "2026-11-08T07:26:00+09:00",
    },
    {
        "title": "국민연금 납부예외 신청 자격과 실업크레딧 활용법",
        "url": "https://www.nesterlog.com/2026/11/70.html",
        "published": "2026-11-07T07:15:00+09:00",
    },
]


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f" — {detail}"))
    if not cond:
        raise AssertionError(name)


def test_image_matching():
    def pick(topic, alt=""):
        return image_pool.pick_image_url(topic=topic, slug="", alt=alt)

    it_url = image_pool._base_url(pick("크롬 브라우저 메모리 부족 에러 캐시 강제 삭제"))
    check("IT 주제 → 노트북/사무실 이미지", it_url in {image_pool._base_url(u) for u in image_pool._IT_IMG}, it_url)

    # 예전에는 'cache' 안의 'ac'에 걸려 에어컨 사진이 붙었다.
    ac_urls = {image_pool._base_url(u) for u in image_pool._AC_IMG} if hasattr(image_pool, "_AC_IMG") else set()
    check("'cache' 가 에어컨 그룹에 오매칭되지 않음", it_url not in ac_urls, it_url)

    admin_url = image_pool._base_url(pick("국민연금 납부예외 신청 자격"))
    check("행정 주제 → 서류 이미지", admin_url in {image_pool._base_url(u) for u in image_pool._ADMIN_IMG}, admin_url)

    mobile_url = image_pool._base_url(pick("아이폰 액정 깨졌을 때 데이터 백업"))
    check("모바일 주제 → 스마트폰 이미지", mobile_url in {image_pool._base_url(u) for u in image_pool._MOBILE_IMG}, mobile_url)

    finance_url = image_pool._base_url(pick("해외 원화결제 DCC 차단 설정"))
    check("금융 주제 → 금융 이미지", finance_url in {image_pool._base_url(u) for u in image_pool._FINANCE_IMG}, finance_url)

    fallback = image_pool._base_url(pick("갑작스러운 손님 맞이"))
    check("분류 불가 주제 → 니치 기본 이미지", fallback in {image_pool._base_url(u) for u in image_pool.FALLBACKS}, fallback)


def test_generate_content():
    main.requests = types.SimpleNamespace(post=fake_post, exceptions=main.requests.exceptions)
    title, body, cat, seo = main.generate_content(
        "국민연금 납부예외 신청",
        "주제목록",
        recent_titles=[],
        recent_posts=RECENT_POSTS,
    )
    check("제목 파싱", title == "실직 후 국민연금 납부예외 신청 자격과 실업크레딧 75% 챙기기", title)
    check("본문에 h1 없음(테마 h1과 중복 방지)", "<h1" not in body.lower(), body[:200])
    check("대표 이미지 1장 삽입", body.count("<img") == 1, body.count("<img"))
    check("이미지 alt 반영", "국민연금공단 전자민원" in body)
    check("관련글 블록 존재", "같이 보면 좋은 글" in body)
    check(
        "관련글은 주제가 가까운 글 우선",
        body.index("국민연금 납부예외 신청 자격과 실업크레딧") < body.index("윈도우11"),
        body[body.find("같이 보면 좋은 글"):][:300],
    )
    check("메타 설명 파싱", bool(seo.get("meta_description")), seo)
    return title, body, seo


def test_publish_body(title, body, seo):
    svc = FakeService()
    main.get_blogger_service = lambda: svc
    ok = main.post_to_blogger(title, body, "디지털 행정·생활", seo)
    check("발행 호출 성공", ok is True)
    sent = svc.sent
    check("본문에 검수용 주석이 남지 않음", "ADSENSE_REVIEW_NOTE" not in sent.get("content", ""),
          sent.get("content", "")[:200])
    check("본문이 주석으로 시작하지 않음", not sent.get("content", "").lstrip().startswith("<!--"),
          sent.get("content", "")[:80])
    check("라벨 1순위 지정", bool(sent.get("labels")), sent.get("labels"))
    check("제목 100자 이내", len(sent.get("title", "")) <= 100)


def test_validate_post(title, body, seo):
    check("정상 글은 발행 전 점검 통과", main.validate_post(title, body, seo) == [],
          main.validate_post(title, body, seo))
    thin = "<article><h2>소제목</h2><p>짧은 글</p></article>"
    problems = main.validate_post("짧음", thin, {"meta_description": "짧음"})
    check("빈약한 글은 차단", len(problems) >= 3, problems)
    dup_h1 = body.replace("<p>", "<h1>중복 제목</h1><p>", 1)
    check("본문 h1 중복 감지", any("h1" in p for p in main.validate_post(title, dup_h1, seo)))


def main_test():
    print("=" * 60)
    test_image_matching()
    title, body, seo = test_generate_content()
    test_publish_body(title, body, seo)
    test_validate_post(title, body, seo)
    print("=" * 60)
    print("전체 통과")


if __name__ == "__main__":
    main_test()
