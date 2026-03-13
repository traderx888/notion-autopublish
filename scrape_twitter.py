"""
Twitter/X Scraper via Apify
Fetches latest tweets from specified accounts or search queries.

Usage:
    python scrape_twitter.py --user @zaborniki --limit 20
    python scrape_twitter.py --search "SPX options gamma" --limit 50
    python scrape_twitter.py --user @zaborniki @dampedspring --limit 10
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

OUTPUT_DIR = Path(__file__).parent / "scraped_data" / "twitter"

# Apify actor: altimis/scweet ($0.30/1K tweets, works on free plan)
TWITTER_ACTOR_ID = "altimis/scweet"


def _get_client():
    """Get authenticated Apify client."""
    from apify_client import ApifyClient

    token = os.getenv("APIFY_TOKEN")
    if not token:
        print("ERROR: APIFY_TOKEN not set in .env")
        sys.exit(1)
    return ApifyClient(token)


def scrape_twitter_user(usernames: list, limit: int = 20) -> list:
    """Scrape latest tweets from one or more Twitter/X users."""
    client = _get_client()
    handles = [f"@{u.lstrip('@')}" for u in usernames]
    print(f"  Scraping {', '.join(handles)} (limit={limit})...")

    run_input = {
        "source_mode": "profiles",
        "profile_urls": handles,
        "max_items": max(limit, 100),  # actor minimum is 100
    }

    try:
        run = client.actor(TWITTER_ACTOR_ID).call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        # Trim to requested limit
        if len(items) > limit:
            items = items[:limit]
        print(f"  Got {len(items)} tweets")
        return items
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def scrape_twitter_search(query: str, limit: int = 50) -> list:
    """Scrape tweets matching a search query."""
    client = _get_client()
    print(f"  Searching: \"{query}\" (limit={limit})...")

    run_input = {
        "source_mode": "search",
        "search_query": query,
        "max_items": max(limit, 100),  # actor minimum is 100
    }

    try:
        run = client.actor(TWITTER_ACTOR_ID).call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        print(f"  Got {len(items)} tweets")
        return items
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def format_tweets(tweets: list) -> str:
    """Format tweets into readable text."""
    lines = []
    for t in tweets:
        # scweet actor field names
        handle = t.get("handle", "") or t.get("user", {}).get("handle", "unknown")
        name = t.get("user", {}).get("name", "")
        text = t.get("text", "") or t.get("full_text", "")
        created = t.get("created_at", "")
        likes = t.get("favorite_count", 0)
        retweets = t.get("retweet_count", 0)
        replies = t.get("reply_count", 0)
        url = t.get("tweet_url", "")

        display = f"@{handle}" + (f" ({name})" if name else "")
        lines.append(display)
        lines.append(f"  {created}")
        lines.append(f"  {text}")
        lines.append(f"  Likes: {likes} | RT: {retweets} | Replies: {replies}")
        if url:
            lines.append(f"  {url}")
        lines.append("")

    return "\n".join(lines)


def save_results(tweets: list, label: str):
    """Save tweets as JSON and formatted text."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace("@", "").replace(" ", "_").replace('"', "")

    # JSON (timestamped)
    json_path = OUTPUT_DIR / f"{safe_label}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False, default=str)

    # Latest JSON (overwrite)
    latest_json = OUTPUT_DIR / f"{safe_label}_latest.json"
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False, default=str)

    # Formatted text
    txt_path = OUTPUT_DIR / f"{safe_label}_latest.txt"
    formatted = format_tweets(tweets)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(formatted)

    print(f"  Saved: {json_path}")
    print(f"  Latest: {latest_json}")
    print(f"  Text: {txt_path}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Twitter/X via Apify")
    parser.add_argument("--user", nargs="+", help="Twitter handles to scrape (e.g. @zaborniki)")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max tweets per user/query")
    args = parser.parse_args()

    if not args.user and not args.search:
        parser.error("Must specify --user or --search")

    print("=" * 50)
    print("Twitter/X Scraper (Apify)")
    print("=" * 50)

    if args.user:
        tweets = scrape_twitter_user(args.user, args.limit)
        label = "_".join(u.lstrip("@") for u in args.user)
        save_results(tweets, label)
    elif args.search:
        tweets = scrape_twitter_search(args.search, args.limit)
        save_results(tweets, args.search[:40])

    print(f"\nTotal: {len(tweets)} tweets")


if __name__ == "__main__":
    main()
