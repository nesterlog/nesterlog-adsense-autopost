"""주제 키워드 → 안정적인 Unsplash CDN 이미지 (핫링크 가능, 무료)."""

import hashlib
import re

# 2026-11 니치 개편(IT 오류·디지털 행정·생활 금융)에 맞춘 대표 이미지.
# 앞 그룹이 우선하며, 글 주제와 맞는 그룹 하나만 사용한다.
_IT_IMG = [
    "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&h=630&q=80",
]
_MOBILE_IMG = [
    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?auto=format&fit=crop&w=1200&h=630&q=80",
]
_ADMIN_IMG = [
    "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&h=630&q=80",
]
_FINANCE_IMG = [
    "https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&h=630&q=80",
]

# (영문/한글 키워드 패턴, Unsplash 직접 URL) — 키워드당 URL을 여러 개 두어 중복 완화
IMAGE_POOL = [
    (
        [
            "윈도우", "윈도우11", "크롬", "브라우저", "캐시", "오류", "에러", "컴퓨터",
            "노트북", "데스크톱", "드라이버", "방화벽", "맥os", "맥북", "작업표시줄",
            "프로그램", "메모리", "업데이트", "설치", "laptop", "computer", "browser",
        ],
        _IT_IMG,
    ),
    (
        [
            "스마트폰", "아이폰", "갤럭시", "휴대폰", "액정", "블루투스", "이어폰",
            "유심", "배터리", "충전", "핫스팟", "nfc", "여권", "사진", "백업",
            "phone", "smartphone", "mobile",
        ],
        _MOBILE_IMG,
    ),
    (
        [
            "정부24", "홈택스", "민원", "서류", "증명", "등본", "신청", "행정", "세금",
            "세액", "소득공제", "연말정산", "보험", "연금", "실업", "급여", "청약",
            "환급", "공제", "계약", "등기", "관리비", "세대",
        ],
        _ADMIN_IMG,
    ),
    (
        [
            "카드", "결제", "수수료", "환불", "은행", "계좌", "적금", "예금", "환전",
            "dcc", "송금", "대출", "이자", "비과세", "페이", "money", "budget", "finance",
        ],
        _FINANCE_IMG,
    ),
    (
        ["health", "cold", "flu", "medical", "면역", "감기", "건강", "병원"],
        [
            "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["sleep", "bed", "night", "수면", "취침", "저녁"],
        [
            "https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["water", "drink", "수분", "물", "hydrate", "습도", "가습", "제습"],
        [
            "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["home", "house", "room", "집", "실내", "청소", "정리", "현관", "신발"],
        [
            "https://images.unsplash.com/photo-1484154218962-a197022b5858?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["kitchen", "food", "cook", "fridge", "냉장고", "요리", "장보기", "식단"],
        [
            "https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["desk", "work", "office", "재택", "책상", "업무", "집중"],
        [
            "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["phone", "battery", "smartphone", "폰", "배터리", "비밀번호"],
        [
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["money", "budget", "bill", "전기요금", "가계", "절약", "지출"],
        [
            "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["laundry", "wash", "세탁", "세탁기"],
        [
            "https://images.unsplash.com/photo-1582735689369-4fe89db7114c?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["morning", "routine", "coffee", "아침", "루틴", "환절기"],
        [
            "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["ac", "aircon", "에어컨", "여름", "냉방"],
        [
            "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["winter", "dry", "피부", "건조", "겨울"],
        [
            "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["delivery", "택배", "중고", "거래"],
        [
            "https://images.unsplash.com/photo-1566576912321-d58ddd7a6088?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
    (
        ["lifestyle", "life", "daily", "생활"],
        [
            "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1511988617509-a57c8a288659?auto=format&fit=crop&w=1200&h=630&q=80",
        ],
    ),
]

DEFAULT_IMAGE = (
    "https://images.unsplash.com/photo-1497366216548-37526070297c"
    "?auto=format&fit=crop&w=1200&h=630&q=80"
)

# 어떤 주제든 어색하지 않은 니치 기본 이미지 (노트북·서류·사무공간·스마트폰·금융·물류)
FALLBACKS = [
    "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1200&h=630&q=80",
]


def _base_url(url: str) -> str:
    """쿼리 제거한 비교용 URL."""
    return (url or "").split("?")[0].rstrip("/")


def _key_hits(key: str, blob: str) -> bool:
    """키워드가 본문 blob에 실제로 등장하는지 검사."""
    key = key.lower()
    if not key:
        return False
    if re.fullmatch(r"[a-z0-9 ]+", key):
        return re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", blob) is not None
    return key in blob


def pick_image_url(
    topic: str = "",
    slug: str = "",
    alt: str = "",
    exclude_urls: set | None = None,
) -> str:
    exclude = {_base_url(u) for u in (exclude_urls or set()) if u}
    blob = f"{topic} {slug} {alt}".lower()
    blob_norm = re.sub(r"[-_/]", " ", blob)

    candidates: list[str] = []
    for keys, urls in IMAGE_POOL:
        # 영문 키는 단어 경계로 검사한다. 'ac'(에어컨)가 'cache' 안에서 걸리는 식의
        # 오매칭을 막기 위함. 한글 키는 부분 일치로 충분하다.
        if any(_key_hits(k, blob_norm) for k in keys):
            if isinstance(urls, str):
                candidates.append(urls)
            else:
                candidates.extend(urls)
            break

    if not candidates:
        candidates = list(FALLBACKS)

    fresh = [u for u in candidates if _base_url(u) not in exclude]
    pool = fresh or [u for u in FALLBACKS if _base_url(u) not in exclude] or FALLBACKS

    # 글마다 다르게 + 제외 반영되도록 해시·제외 개수를 섞음
    salt = f"{blob}|{len(exclude)}|{','.join(sorted(exclude)[:5])}"
    idx = int(hashlib.md5(salt.encode("utf-8")).hexdigest(), 16) % len(pool)
    return pool[idx]


def featured_image_html(
    alt_text: str,
    topic: str = "",
    slug: str = "",
    exclude_urls: set | None = None,
) -> str:
    alt = (alt_text or topic or "대표 이미지").replace('"', "")
    src = pick_image_url(
        topic=topic, slug=slug, alt=alt, exclude_urls=exclude_urls
    )
    return (
        '<figure class="featured-image" style="margin:0 0 1.5em 0;">'
        f'<img src="{src}" alt="{alt}" width="1200" height="630" '
        'style="max-width:100%;height:auto;border-radius:8px;" loading="lazy" />'
        f'<figcaption style="font-size:0.9em;color:#666;">{alt}</figcaption>'
        "</figure>"
    )
