"""기존 초안 1건: 카테고리 문구 제거, 라벨 정리, 대표이미지 추가 후 공개."""
import os
import re
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


def clean_body(html: str, title: str) -> str:
    html = re.sub(
        r'<p class="meta">.*?</p>',
        "",
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"<p[^>]*>\s*<strong>카테고리:.*?</strong>.*?</p>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(r"<strong>카테고리:.*?</strong>\s*\|?\s*", "", html)
    html = re.sub(r"카테고리:\s*생활정보[^|<]*", "", html)
    # ADSENSE 주석 정리
    html = re.sub(r"<!--\s*ADSENSE_REVIEW_NOTE.*?-->", "", html, flags=re.DOTALL)

    if not re.search(r"<img\s", html, re.IGNORECASE):
        img = featured_image_html(title, topic=title, slug="health,cold,home")
        if "</h1>" in html:
            html = html.replace("</h1>", "</h1>\n" + img, 1)
        else:
            html = img + "\n" + html
    return html.strip()


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
    drafts = (
        svc.posts()
        .list(blogId=blog_id, status="DRAFT", maxResults=20, fetchBodies=True)
        .execute()
        .get("items")
        or []
    )
    if not drafts:
        print("정리할 초안 없음")
        return

    for post in drafts:
        pid = post["id"]
        title = post.get("title") or "생활 가이드"
        body = clean_body(post.get("content") or "", title)
        labels = ["생활정보와 실용 가이드", "생활꿀팁"]
        if "감기" in title or "환절기" in title:
            labels.append("환절기 건강")
        labels = labels[:3]

        updated = {
            "kind": "blogger#post",
            "id": pid,
            "title": title,
            "content": body,
            "labels": labels,
        }
        svc.posts().update(blogId=blog_id, postId=pid, body=updated).execute()
        published = svc.posts().publish(blogId=blog_id, postId=pid).execute()
        print("정리 후 발행:", published.get("title"))
        print("URL:", published.get("url"))
        print("라벨:", labels)


if __name__ == "__main__":
    main()
