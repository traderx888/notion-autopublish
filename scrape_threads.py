"""
Meta Threads Scraper via Apify
Fetches latest posts from specified Threads accounts.

Usage:
    python scrape_threads.py --user @zuck --limit 20
    python scrape_threads.py --user @zuck @mosseri --limit 10
    python scrape_threads.py --search "AI trading" --limit 50
"""

import argparse
import json
import os
import sys
import io
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Load .env from this project or fundman-jarvis
load_dotenv()
JARVIS_ENV = Path(r"c:\Users\User\Documents\GitHub\fundman-jarvis\.env")
if JARVIS_ENV.exists():
    load_dotenv(JARVIS_ENV)

OUTPUT_DIR = Path(__file__).parent / "scraped_data" / "threads"

# Apify actor: futurizerush/meta-threads-scraper ($0.01/result, no login required)
THREADS_ACTOR_ID = "futurizerush/meta-threads-scraper"


def _get_client():
    """Get authenticated Apify client."""
    from apify_client import ApifyClient

    token = os.getenv("APIFY_TOKEN")
    if not token:
        print("ERROR: APIFY_TOKEN not set in .env")
        sys.exit(1)
    return ApifyClient(token)


def scrape_threads_user(usernames: list, limit: int = 20) -> list:
    """Scrape latest posts from one or more Threads users."""
    client = _get_client()
    handles = [u.lstrip("@") for u in usernames]
    print(f"  Scraping @{', @'.join(handles)} (limit={limit} per user)...")

    run_input = {
        "mode": "user",
        "usernames": handles,
        "max_posts": limit,
    }

    try:
        run = client.actor(THREADS_ACTOR_ID).call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        print(f"  Got {len(items)} posts total")
        return items
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def scrape_threads_search(query: str, limit: int = 50) -> list:
    """Scrape Threads posts matching a keyword search."""
    client = _get_client()
    print(f"  Searching: \"{query}\" (limit={limit})...")

    run_input = {
        "mode": "search",
        "keywords": [query],
        "search_filter": "Recent",
        "max_posts": limit,
    }

    try:
        run = client.actor(THREADS_ACTOR_ID).call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        print(f"  Got {len(items)} posts")
        return items
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def format_posts(posts: list) -> str:
    """Format Threads posts into readable text."""
    lines = []
    for p in posts:
        handle = p.get("username") or p.get("ownerUsername", "unknown")
        text = p.get("text_content") or p.get("text") or p.get("caption", "")
        created = p.get("created_at_display") or p.get("created_at") or p.get("createdAt", "")
        likes = p.get("like_count") or p.get("likeCount", 0)
        replies = p.get("reply_count") or p.get("replyCount", 0)
        reposts = p.get("repost_count") or p.get("repostCount", 0)
        url = p.get("post_url") or p.get("url", "")

        lines.append(f"@{handle}")
        lines.append(f"  {created}")
        lines.append(f"  {text}")
        lines.append(f"  Likes: {likes} | Replies: {replies} | Reposts: {reposts}")
        if url:
            lines.append(f"  {url}")
        lines.append("")

    return "\n".join(lines)


def save_results(posts: list, label: str):
    """Save posts as JSON and formatted text."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace("@", "").replace(" ", "_").replace('"', "")

    # JSON (timestamped)
    json_path = OUTPUT_DIR / f"{safe_label}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False, default=str)

    # Latest JSON (overwrite)
    latest_json = OUTPUT_DIR / f"{safe_label}_latest.json"
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False, default=str)

    # Formatted text
    txt_path = OUTPUT_DIR / f"{safe_label}_latest.txt"
    formatted = format_posts(posts)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(formatted)

    print(f"  Saved: {json_path}")
    print(f"  Latest: {latest_json}")
    print(f"  Text: {txt_path}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Meta Threads via Apify")
    parser.add_argument("--user", nargs="+", help="Threads handles to scrape (e.g. @zuck)")
    parser.add_argument("--search", type=str, help="Search keyword")
    parser.add_argument("--limit", type=int, default=20, help="Max posts per user/keyword")
    args = parser.parse_args()

    if not args.user and not args.search:
        parser.error("Must specify --user or --search")

    print("=" * 50)
    print("Threads Scraper (Apify)")
    print("=" * 50)

    if args.user:
        posts = scrape_threads_user(args.user, args.limit)
        label = "_".join(u.lstrip("@") for u in args.user)
        save_results(posts, label)
    elif args.search:
        posts = scrape_threads_search(args.search, args.limit)
        save_results(posts, args.search[:40])

    print(f"\nTotal: {len(posts)} posts")


if __name__ == "__main__":
    main()
