"""깨진 이미지 글 수정: Unsplash 이미지 + 본문 자연스럽게 다듬어 업데이트."""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from image_pool import featured_image_html


def load_env():
    raw = Path(".env").read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


TITLE = "환절기 감기, 하루 루틴으로 막는 현실적인 방법"

CONTENT = f"""
<article>
<h1>{TITLE}</h1>
{featured_image_html("따뜻한 차와 함께하는 환절기 건강 루틴", topic="환절기 감기 예방 아침 루틴", slug="cold-prevention-morning")}

<section>
<p>환절기만 되면 목이 칼칼해지거나 콧물이 나는 분들이 많아요. 저도 기온 차가 큰 주간에는 컨디션이 금방 흔들렸습니다. 약에만 기대기보다, <strong>환절기 감기 예방</strong>은 결국 아침·낮·밤의 작은 습관 차이가 크더라고요.</p>
<p>거창한 비법 없이, 오늘부터 바로 해볼 수 있는 하루 루틴만 정리했습니다.</p>
</section>

<section>
<h2>아침: 체온부터 챙기기</h2>
<p>일어나자마자 찬물에 손을 담그거나 맨발로 차가운 바닥을 밟으면 몸이 움츠러듭니다. 저는 이렇게 바꿨어요.</p>
<ul>
<li>기상 후 미지근한 물 한 잔 — 밤새 마른 목을 먼저 적십니다.</li>
<li>양말이나 실내화를 바로 신기 — 발끝이 차가우면 하루 종일 몸이 둔해집니다.</li>
<li>옷을 얇게 여러 겹 — 더우면 벗고, 추우면 입는 식이 체온 유지에 편합니다.</li>
</ul>
</section>

<section>
<h2>낮: 손 위생과 실내 공기</h2>
<p>낮에는 사람·물건 접촉이 많습니다. 외출 후·식사 전·얼굴을 만지기 전에는 손 씻기를 우선으로 합니다. 세정제가 있으면 보조로 쓰고, 가능하면 비누와 물로 꼼꼼히 씻는 편이 낫습니다.</p>
<p>집이나 사무실은 온도 20~22℃, 습도 40~60% 정도가 숨쉬기 편합니다. 가습기가 부담되면 물에 적신 수건을 걸어두는 것만으로도 건조함이 줄어듭니다. 창문은 낮에 짧게라도 2~3번 열어 환기하세요.</p>
</section>

<section>
<h2>저녁: 과하게 안 하고, 잘 자기</h2>
<p>밤늦게 자극적인 야식을 먹으면 잠이 얕아지고 다음날 목이 더 피곤합니다. 잠들기 1~2시간 전 따뜻한 물로 가볍게 씻거나 족욕을 하면 몸이 풀리는 느낌이 납니다.</p>
<ul>
<li>취침 전 과식은 피하기</li>
<li>머리맡이 너무 건조하지 않게 유지</li>
<li>가능하면 하루 7시간 전후 수면</li>
</ul>
</section>

<section>
<h2>자주 묻는 질문</h2>
<p><strong>Q. 영양제만 먹으면 감기를 막을 수 있나요?</strong><br>
비타민은 보조일 뿐입니다. 수면·습도·손 위생이 먼저입니다.</p>
<p><strong>Q. 가습기 없으면 어떻게 하나요?</strong><br>
젖은 수건, 빨래 널기, 물컵을 방 안에 두는 방법도 도움이 됩니다.</p>
<p><strong>Q. 운동은 실내가 나을까요?</strong><br>
컨디션이 좋을 때는 가벼운 야외 산책도 괜찮습니다. 목이 이미 불편하면 무리한 운동은 쉬는 편이 낫습니다.</p>
</section>

<section>
<h2>정리</h2>
<p>환절기 감기 예방의 핵심은 거창한 건강법이 아니라, <strong>체온·수분·습도·수면</strong>을 하루 리듬에 맞춰 지키는 일입니다. 오늘 아침 미지근한 물 한 잔부터 시작해 보세요.</p>
<p>비슷한 고민이 있다면 댓글로 남겨 주세요.</p>
</section>
</article>
""".strip()


def main():
    load_env()
    blog_id = os.environ.get("BLOGGER_BLOG_ID") or "1587705316274533593"
    post_id = "493432194999615368"
    creds = Credentials(
        None,
        refresh_token=os.environ["G_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["G_CLIENT_ID"],
        client_secret=os.environ["G_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    svc = build("blogger", "v3", credentials=creds)
    body = {
        "kind": "blogger#post",
        "id": post_id,
        "title": TITLE,
        "content": CONTENT,
        "labels": ["생활꿀팁", "환절기 건강"],
    }
    result = svc.posts().update(blogId=blog_id, postId=post_id, body=body).execute()
    print("UPDATED", result.get("title"))
    print("URL", result.get("url"))
    print("LABELS", result.get("labels"))
    # verify image
    import re
    import requests

    srcs = re.findall(r'src="([^"]+)"', result.get("content") or "")
    for s in srcs:
        r = requests.get(s, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        print("IMG_OK", r.status_code, r.headers.get("content-type"), s[:90])


if __name__ == "__main__":
    main()
