"""
Notion → Auto Publisher
從 Notion Content Calendar 自動發布到 Threads / LinkedIn / Patreon

用法:
    python publish.py              # 發布今天 Status=Ready 的內容
    python publish.py --dry-run    # 預覽模式，不會真的發布
    python publish.py --date 2026-03-01  # 指定日期
"""

import os
import re
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_PERSON_ID = os.getenv("LINKEDIN_PERSON_ID")

PATREON_ACCESS_TOKEN = os.getenv("PATREON_ACCESS_TOKEN")
PATREON_CAMPAIGN_ID = os.getenv("PATREON_CAMPAIGN_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


# ─── Notion 讀取 ──────────────────────────────────────────────
def query_ready_posts(target_date: str) -> list:
    """查詢 Notion 中 Status=Ready 且 Publish Date=target_date 的頁面"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Status", "select": {"equals": "Ready"}},
                {"property": "Publish Date", "date": {"equals": target_date}},
            ]
        }
    }
    resp = requests.post(url, headers=NOTION_HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_page_content(page_id: str) -> str:
    """從 Notion 頁面提取純文字內容"""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
    resp = requests.get(url, headers=NOTION_HEADERS)
    resp.raise_for_status()

    blocks = resp.json().get("results", [])
    lines = []

    for block in blocks:
        btype = block.get("type", "")
        data = block.get(btype, {})
        rich_text = data.get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich_text)

        if btype == "paragraph":
            lines.append(text)
        elif btype in ("heading_1", "heading_2", "heading_3"):
            lines.append(text)
        elif btype == "bulleted_list_item":
            lines.append(f"• {text}")
        elif btype == "numbered_list_item":
            lines.append(f"- {text}")
        elif btype == "table_row":
            cells = data.get("cells", [])
            row = " | ".join(
                "".join(rt.get("plain_text", "") for rt in cell) for cell in cells
            )
            lines.append(row)
        elif btype == "divider":
            lines.append("---")

    return "\n".join(lines).strip()


def parse_page(page: dict) -> dict:
    """解析 Notion 頁面 metadata"""
    props = page["properties"]
    title_arr = props.get("Title", {}).get("title", [])
    title = "".join(t.get("plain_text", "") for t in title_arr)
    content_type = props.get("Content Type", {}).get("select", {}).get("name", "")
    page_id = page["id"]
    return {"page_id": page_id, "title": title, "content_type": content_type}


def update_status(page_id: str, status: str):
    """更新 Notion 頁面 Status"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Status": {"select": {"name": status}}}}
    resp = requests.patch(url, headers=NOTION_HEADERS, json=payload)
    resp.raise_for_status()
    print(f"  ✅ Notion Status → {status}")


# ─── Threads 發布 ─────────────────────────────────────────────
def publish_threads_single(text: str) -> str:
    """發布單篇 Threads 貼文，回傳 media_id"""
    # Step 1: Create container
    url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    resp = requests.post(
        url,
        params={"access_token": THREADS_ACCESS_TOKEN},
        json={"media_type": "TEXT", "text": text},
    )
    resp.raise_for_status()
    creation_id = resp.json()["id"]

    # Step 2: Wait for processing
    time.sleep(5)

    # Step 3: Publish
    pub_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    resp = requests.post(
        pub_url,
        params={"access_token": THREADS_ACCESS_TOKEN},
        json={"creation_id": creation_id},
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    print(f"  🧵 Threads 發布成功 (ID: {media_id})")
    return media_id


def publish_threads_thread(text: str):
    """發布 Threads 串文（自動拆分並依序回覆）"""
    # 用 (1/N), (2/N) 等模式拆分
    parts = re.split(r"\n*\*?\*?\(?\d+/\d+\)?\*?\*?\s+", text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= 1:
        # fallback: 用雙換行拆
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not parts:
        print("  ⚠️ Thread 內容為空，跳過")
        return

    print(f"  🧵 Thread 共 {len(parts)} 段")

    # 發布第一篇
    reply_to_id = publish_threads_single(parts[0])

    # 後續每篇 reply 到上一篇
    for i, part in enumerate(parts[1:], start=2):
        time.sleep(5)  # Threads API rate limit
        url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        resp = requests.post(
            url,
            params={"access_token": THREADS_ACCESS_TOKEN},
            json={
                "media_type": "TEXT",
                "text": part,
                "reply_to_id": reply_to_id,
            },
        )
        resp.raise_for_status()
        creation_id = resp.json()["id"]

        time.sleep(5)

        pub_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
        resp = requests.post(
            pub_url,
            params={"access_token": THREADS_ACCESS_TOKEN},
            json={"creation_id": creation_id},
        )
        resp.raise_for_status()
        reply_to_id = resp.json()["id"]
        print(f"  🧵 Thread ({i}/{len(parts)}) 發布成功")


# ─── LinkedIn 發布 ────────────────────────────────────────────
def publish_linkedin(text: str):
    """發布 LinkedIn 貼文"""
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": LINKEDIN_PERSON_ID,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    post_id = resp.json().get("id", "unknown")
    print(f"  💼 LinkedIn 發布成功 (ID: {post_id})")


# ─── Patreon 發布 ─────────────────────────────────────────────
def publish_patreon(title: str, text: str):
    """發布 Patreon 文章"""
    url = "https://www.patreon.com/api/oauth2/v2/posts"
    headers = {
        "Authorization": f"Bearer {PATREON_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "type": "post",
            "attributes": {
                "title": title,
                "content": text,
                "is_paid": False,
                "is_draft": False,
                "post_type": "text_only",
            },
            "relationships": {
                "campaign": {
                    "data": {"type": "campaign", "id": PATREON_CAMPAIGN_ID}
                }
            },
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    post_id = resp.json().get("data", {}).get("id", "unknown")
    print(f"  🅿️ Patreon 發布成功 (ID: {post_id})")


# ─── 路由 ─────────────────────────────────────────────────────
def publish_post(content_type: str, title: str, text: str, dry_run: bool = False):
    """根據 Content Type 路由到對應平台"""
    if dry_run:
        print(f"  🔍 [DRY RUN] 會發布到: {content_type}")
        print(f"  📝 標題: {title}")
        print(f"  📏 字數: {len(text)}")
        print(f"  📄 前 100 字: {text[:100]}...")
        return True

    try:
        if content_type == "Twitter":
            publish_threads_single(text)
        elif content_type == "LinkedIn":
            publish_linkedin(text)
        elif content_type == "Newsletter":
            publish_patreon(title, text)
        elif content_type == "Thread":
            publish_threads_thread(text)
        else:
            print(f"  ⚠️ 未知 Content Type: {content_type}，跳過")
            return False
        return True
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ 發布失敗: {e}")
        print(f"  Response: {e.response.text if e.response else 'N/A'}")
        return False


# ─── 主流程 ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Notion → Auto Publisher")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不實際發布")
    parser.add_argument("--date", type=str, default=None, help="指定日期 YYYY-MM-DD")
    args = parser.parse_args()

    # 用 HKT 時區
    hkt = timezone(timedelta(hours=8))
    target_date = args.date or datetime.now(hkt).strftime("%Y-%m-%d")

    print(f"{'='*50}")
    print(f"📅 Notion Auto Publisher")
    print(f"📅 目標日期: {target_date}")
    print(f"🔍 模式: {'DRY RUN (預覽)' if args.dry_run else 'LIVE (實際發布)'}")
    print(f"{'='*50}\n")

    # 檢查必要 token
    if not NOTION_TOKEN:
        print("❌ 缺少 NOTION_TOKEN，請檢查 .env")
        sys.exit(1)

    # 查詢 Notion
    posts = query_ready_posts(target_date)
    print(f"📋 找到 {len(posts)} 篇待發布內容\n")

    if not posts:
        print("🎉 沒有需要發布的內容，結束")
        return

    success_count = 0
    fail_count = 0

    for i, page in enumerate(posts, 1):
        meta = parse_page(page)
        print(f"[{i}/{len(posts)}] {meta['content_type']}: {meta['title']}")

        # 取得頁面內容
        text = get_page_content(meta["page_id"])
        if not text:
            print("  ⚠️ 頁面內容為空，跳過")
            fail_count += 1
            continue

        # 發布
        ok = publish_post(meta["content_type"], meta["title"], text, args.dry_run)

        if ok and not args.dry_run:
            update_status(meta["page_id"], "Published")
            success_count += 1
        elif ok:
            success_count += 1
        else:
            fail_count += 1

        print()

    # 結果摘要
    print(f"{'='*50}")
    print(f"✅ 成功: {success_count}  ❌ 失敗: {fail_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
