"""소개(About) 페이지를 생활꿀팁 니치에 맞게 채우고, CNAME 글 라벨을 정리합니다."""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


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


ABOUT_HTML = """
<div class="about-page">
<h2>네스터 소개</h2>
<p>안녕하세요. <strong>네스터로그(nesterlog.com)</strong>를 운영하는 네스터입니다.</p>
<p>이 블로그는 거창한 전문 정보가 아니라, <strong>일상에서 바로 써먹을 수 있는 생활 꿀팁</strong>을 모아 두는 공간입니다. 집 관리, 절약, 자취·직장인 루틴처럼 직접 해보고 도움이 됐던 방법을 짧고 실용적으로 정리합니다.</p>
<h3>이런 글을 올립니다</h3>
<ul>
<li>집·생활 정리와 관리 팁</li>
<li>절약·가계에 도움 되는 현실적인 방법</li>
<li>환절기·컨디션 같은 생활 건강 루틴</li>
<li>초보자도 따라 하기 쉬운 체크리스트</li>
</ul>
<p>모든 글은 개인적인 경험과 조사를 바탕으로 작성하며, 의료·법률·투자 등 전문 상담을 대체하지 않습니다. 틀린 점이나 더 좋은 방법이 있으면 댓글·문의로 알려 주세요.</p>
<p>문의: <a href="https://www.nesterlog.com/p/disclaimer.html">연락처 페이지</a>를 이용해 주세요.</p>
</div>
""".strip()


def main():
    load_env()
    blog_id = os.environ.get("BLOGGER_BLOG_ID") or "1587705316274533593"
    creds = Credentials(
        None,
        refresh_token=os.environ["G_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["G_CLIENT_ID"],
        client_secret=os.environ["G_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    svc = build("blogger", "v3", credentials=creds)

    # About 페이지 업데이트
    pages = (
        svc.pages()
        .list(blogId=blog_id, fetchBodies=True, maxResults=20)
        .execute()
        .get("items")
        or []
    )
    about = None
    for p in pages:
        title = p.get("title") or ""
        url = p.get("url") or ""
        if "about" in url.lower() or "소개" in title or "About" in title:
            about = p
            break
    if not about:
        raise SystemExit("About 페이지를 찾지 못했습니다.")

    updated = {
        "kind": "blogger#page",
        "id": about["id"],
        "title": about.get("title") or "소개(About)",
        "content": ABOUT_HTML,
    }
    res = svc.pages().update(blogId=blog_id, pageId=about["id"], body=updated).execute()
    print("ABOUT_UPDATED", res.get("url"))

    # CNAME 글: 라벨을 '블로그운영'으로 유지 (생활꿀팁으로 억지 분류하지 않음)
    # 검색 설명용으로 본문은 건드리지 않고 라벨만 명확히
    cname_id = "4018191393354894101"
    post = svc.posts().get(blogId=blog_id, postId=cname_id).execute()
    body = {
        "kind": "blogger#post",
        "id": cname_id,
        "title": post.get("title"),
        "content": post.get("content"),
        "labels": ["블로그운영"],
    }
    post_res = svc.posts().update(blogId=blog_id, postId=cname_id, body=body).execute()
    print("CNAME_LABELS", post_res.get("labels"))
    print("CNAME_URL", post_res.get("url"))
    print("OK")


if __name__ == "__main__":
    main()
