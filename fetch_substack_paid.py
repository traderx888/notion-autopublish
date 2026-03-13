"""
Fetch paid Substack articles using Chrome cookies directly (no Playwright needed).
Uses rookiepy to decrypt Chrome's DPAPI-encrypted cookies.
"""

import json
import sys
import rookiepy
import requests
from pathlib import Path

SCRAPED_DIR = Path(__file__).parent / "scraped_data" / "substack_authors"
SCRAPED_DIR.mkdir(parents=True, exist_ok=True)


def get_substack_cookies() -> dict:
    """Extract Substack cookies from Chrome."""
    cookies = rookiepy.chrome(domains=["substack.com", ".substack.com"])
    cookie_dict = {}
    for c in cookies:
        cookie_dict[c["name"]] = c["value"]
    print(f"  Found {len(cookie_dict)} Substack cookies")
    return cookie_dict


def fetch_article(url: str, cookies: dict) -> dict:
    """Fetch a Substack article with authenticated cookies."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)
    resp.raise_for_status()

    # Try the Substack API endpoint for full post content
    # Substack articles have a JSON+LD or API endpoint
    from html.parser import HTMLParser
    import re

    html = resp.text
    title = ""
    title_match = re.search(r'<h1[^>]*class="post-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            title = title_match.group(1).strip()

    date = ""
    date_match = re.search(r'<time[^>]*datetime="([^"]*)"', html)
    if date_match:
        date = date_match.group(1)

    # Extract the full post body
    body_text = ""

    # Method 1: Try finding the body markup div
    body_match = re.search(
        r'<div[^>]*class="[^"]*body markup[^"]*"[^>]*>(.*?)</div>\s*</div>\s*<div[^>]*class="[^"]*post-footer',
        html, re.S
    )
    if not body_match:
        body_match = re.search(
            r'<div[^>]*class="[^"]*body markup[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*subscription)',
            html, re.S
        )
    if not body_match:
        # Broader match
        body_match = re.search(
            r'<div[^>]*class="[^"]*body markup[^"]*"[^>]*>(.*?)</div>',
            html, re.S
        )

    if body_match:
        raw_html = body_match.group(1)
        # Strip HTML tags for text
        body_text = re.sub(r'<[^>]+>', ' ', raw_html)
        body_text = re.sub(r'\s+', ' ', body_text).strip()

    # Method 2: Try Substack's API
    if len(body_text) < 500:
        # Extract slug from URL
        slug_match = re.search(r'/p/([^/?#]+)', url)
        if slug_match:
            slug = slug_match.group(1)
            # Try the API endpoint
            subdomain_match = re.search(r'https?://([^.]+)\.substack\.com', url)
            if subdomain_match:
                subdomain = subdomain_match.group(1)
                api_url = f"https://{subdomain}.substack.com/api/v1/posts/{slug}"
                try:
                    api_resp = requests.get(api_url, headers=headers, cookies=cookies, timeout=30)
                    if api_resp.status_code == 200:
                        data = api_resp.json()
                        body_html = data.get("body_html", "")
                        if body_html:
                            body_text = re.sub(r'<[^>]+>', ' ', body_html)
                            body_text = re.sub(r'\s+', ' ', body_text).strip()
                        if not title:
                            title = data.get("title", "")
                        if not date:
                            date = data.get("post_date", "")
                        print(f"    Got full content via API ({len(body_text)} chars)")
                except Exception as e:
                    print(f"    API fallback failed: {e}")

    return {
        "url": url,
        "title": title,
        "date": date,
        "body_text": body_text,
        "char_count": len(body_text),
    }


def get_author_posts(author_url: str, cookies: dict, limit: int = 5) -> list[str]:
    """Get post URLs from an author's profile page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    resp = requests.get(author_url, headers=headers, cookies=cookies, timeout=30)
    import re
    # Find all /p/ links
    urls = re.findall(r'href="(https://[^"]*\.substack\.com/p/[^"?#]+)"', resp.text)
    seen = []
    for u in urls:
        if u not in seen:
            seen.append(u)
        if len(seen) >= limit:
            break
    return seen


if __name__ == "__main__":
    author_url = sys.argv[1] if len(sys.argv) > 1 else "https://substack.com/@capitalwars"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print("  Extracting Chrome cookies...")
    cookies = get_substack_cookies()

    print(f"  Fetching post list from: {author_url}")
    post_urls = get_author_posts(author_url, cookies, limit=limit)
    print(f"  Found {len(post_urls)} posts")

    articles = []
    for i, url in enumerate(post_urls, 1):
        print(f"  [{i}/{len(post_urls)}] {url}")
        try:
            art = fetch_article(url, cookies)
            articles.append(art)
            print(f"    Title: {art['title'][:60]}")
            print(f"    Content: {art['char_count']} chars")
        except Exception as e:
            print(f"    ERROR: {e}")

    # Save combined output
    combined_path = SCRAPED_DIR / "capitalwars_latest.txt"
    combined = []
    for art in articles:
        combined.append(f"{'='*60}")
        combined.append(f"TITLE: {art['title']}")
        combined.append(f"DATE: {art['date']}")
        combined.append(f"URL: {art['url']}")
        combined.append(f"{'='*60}")
        combined.append(art["body_text"])
        combined.append("\n")
    combined_path.write_text("\n".join(combined), encoding="utf-8")

    # Save individual JSON
    for art in articles:
        slug = art["title"].lower().replace(" ", "-")[:50]
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        if slug:
            fp = SCRAPED_DIR / f"{slug}.json"
            fp.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  Saved {len(articles)} articles to: {SCRAPED_DIR}")
    print(f"  Combined: {combined_path}")
