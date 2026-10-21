"""주제 키워드 → 안정적인 Unsplash CDN 이미지 (핫링크 가능, 무료)."""

import hashlib
import re

# (영문 키워드 패턴, Unsplash 직접 URL) — LoremFlickr처럼 깨지지 않는 고정 CDN
IMAGE_POOL = [
    (
        ["health", "cold", "flu", "medical", "면역", "감기", "건강", "병원"],
        "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["sleep", "bed", "night", "수면", "취침", "저녁"],
        "https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["water", "drink", "수분", "물", "hydrate"],
        "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["home", "house", "room", "집", "실내", "청소", "정리"],
        "https://images.unsplash.com/photo-1484154218962-a197022b5858?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["kitchen", "food", "cook", "fridge", "냉장고", "요리", "장보기"],
        "https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["desk", "work", "office", "재택", "책상", "업무"],
        "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["phone", "battery", "smartphone", "폰", "배터리"],
        "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["money", "budget", "bill", "전기요금", "가계", "절약"],
        "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["laundry", "wash", "세탁"],
        "https://images.unsplash.com/photo-1582735689369-4fe89db7114c?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["morning", "routine", "coffee", "아침", "루틴"],
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
    (
        ["lifestyle", "life", "daily", "생활"],
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&h=630&q=80",
    ),
]

DEFAULT_IMAGE = (
    "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e"
    "?auto=format&fit=crop&w=1200&h=630&q=80"
)

# 같은 키워드여도 글마다 조금씩 다르게 보이도록 예비 이미지
FALLBACKS = [
    "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1511988617509-a57c8a288659?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?auto=format&fit=crop&w=1200&h=630&q=80",
    "https://picsum.photos/id/292/1200/630.jpg",
    "https://picsum.photos/id/326/1200/630.jpg",
]


def pick_image_url(topic: str = "", slug: str = "", alt: str = "") -> str:
    blob = f"{topic} {slug} {alt}".lower()
    blob_norm = re.sub(r"[-_/]", " ", blob)
    matches = []
    for keys, url in IMAGE_POOL:
        if any(k.lower() in blob_norm for k in keys):
            matches.append(url)
    if matches:
        # 주제 맞으면서 글마다 고정되도록 해시로 선택
        idx = int(hashlib.md5(blob.encode("utf-8")).hexdigest(), 16) % len(matches)
        return matches[idx]
    idx = int(hashlib.md5(blob.encode("utf-8")).hexdigest(), 16) % len(FALLBACKS)
    return FALLBACKS[idx]


def featured_image_html(alt_text: str, topic: str = "", slug: str = "") -> str:
    alt = (alt_text or topic or "대표 이미지").replace('"', "")
    src = pick_image_url(topic=topic, slug=slug, alt=alt)
    return (
        '<figure class="featured-image" style="margin:0 0 1.5em 0;">'
        f'<img src="{src}" alt="{alt}" width="1200" height="630" '
        'style="max-width:100%;height:auto;border-radius:8px;" loading="lazy" />'
        f'<figcaption style="font-size:0.9em;color:#666;">{alt}</figcaption>'
        "</figure>"
    )
