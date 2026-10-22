"""주제 키워드 → 안정적인 Unsplash CDN 이미지 (핫링크 가능, 무료)."""

import hashlib
import re

# (영문 키워드 패턴, Unsplash 직접 URL) — 키워드당 URL을 여러 개 두어 중복 완화
IMAGE_POOL = [
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
            "https://images.unsplash.com/photo-1527489377706-95ea4f4d54c6?auto=format&fit=crop&w=1200&h=630&q=80",
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
            "https://images.unsplash.com/photo-1517677208171-e172fc623200?auto=format&fit=crop&w=1200&h=630&q=80",
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
        ["recycle", "분리수거", "쓰레기"],
        [
            "https://images.unsplash.com/photo-1532996122724-e3c354a0b4bd?auto=format&fit=crop&w=1200&h=630&q=80",
            "https://images.unsplash.com/photo-1611284446314-60a58ac0deb8?auto=format&fit=crop&w=1200&h=630&q=80",
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
    "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e"
    "?auto=format&fit=crop&w=1200&h=630&q=80"
)

FALLBACKS = [
    "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1511988617509-a57c8a288659?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1484480974693-6ca0a78fb36b?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://picsum.photos/id/292/1200/630.jpg",
    "https://picsum.photos/id/326/1200/630.jpg",
    "https://picsum.photos/id/1015/1200/630.jpg",
    "https://picsum.photos/id/201/1200/630.jpg",
]


def _base_url(url: str) -> str:
    """쿼리 제거한 비교용 URL."""
    return (url or "").split("?")[0].rstrip("/")


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
        if any(k.lower() in blob_norm for k in keys):
            if isinstance(urls, str):
                candidates.append(urls)
            else:
                candidates.extend(urls)

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
