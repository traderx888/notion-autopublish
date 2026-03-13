"""
Quick script to scrape a specific Substack author's recent posts
using the existing persistent browser session.
"""

import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding for CJK/emoji characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

from browser.base import BrowserAutomation, SCRAPED_DIR


class SubstackAuthorReader(BrowserAutomation):
    SERVICE_NAME = "substack"
    USE_CHROME_PROFILE = False  # use existing Playwright session (already logged in)

    def is_logged_in(self) -> bool:
        return True

    def login(self):
        pass

    def read_author_page(self, url: str, limit: int = 5) -> list[dict]:
        print(f"  Navigating to: {url}")
        self.page.goto(url, wait_until="networkidle")
        self.page.wait_for_timeout(5000)

        # Collect post links from the author profile
        post_links = []
        links = self.page.locator('a[href*="/p/"]')
        seen = set()

        for i in range(links.count()):
            href = links.nth(i).get_attribute("href") or ""
            if href and "/p/" in href and href not in seen:
                seen.add(href)
                title_el = links.nth(i).locator("h2, h3, [class*='title']").first
                title = title_el.inner_text().strip() if title_el.count() > 0 else ""
                if not title:
                    title = links.nth(i).inner_text().strip()[:100]
                full_url = href if href.startswith("http") else f"https://{href.lstrip('/')}"
                post_links.append({"url": full_url, "title": title})

            if len(post_links) >= limit:
                break

        print(f"  Found {len(post_links)} posts")

        # Scrape each post's full content
        articles = []
        for i, post in enumerate(post_links, 1):
            print(f"  [{i}/{len(post_links)}] {post['title'][:60]}")
            try:
                self.page.goto(post["url"], wait_until="networkidle")
                self.page.wait_for_timeout(3000)

                # Try to click through paywall gate if present
                claim_btn = self.page.locator(
                    'a:has-text("Claim my free post"), '
                    'button:has-text("Claim my free post"), '
                    'a:has-text("Continue reading"), '
                    'button:has-text("Continue reading")'
                ).first
                if claim_btn.count() > 0:
                    print("    Clicking through paywall gate...")
                    claim_btn.click()
                    self.page.wait_for_timeout(5000)

                # Check if we're logged in by looking for subscriber content
                paywall_still = self.page.locator(
                    'text="Subscribe",'
                    '[class*="paywall"],'
                    'text="purchase a paid subscription"'
                )
                if paywall_still.count() > 0:
                    # Try checking if login is needed
                    print("    Still paywalled, checking login state...")
                    self.screenshot(f"substack_paywall_{i}")

                title = ""
                if self.page.locator("h1").count() > 0:
                    title = self.page.locator("h1").first.inner_text().strip()

                date_str = ""
                date_el = self.page.locator("time, [datetime]").first
                if date_el.count() > 0:
                    date_str = date_el.get_attribute("datetime") or date_el.inner_text()

                # Try multiple selectors for the full article body
                body_text = ""
                for sel in [
                    '.body.markup',
                    '[class*="post-content"]',
                    '.available-content',
                    '[class*="body"]',
                    'article',
                ]:
                    el = self.page.locator(sel).first
                    if el.count() > 0:
                        text = el.inner_text()
                        if len(text) > len(body_text):
                            body_text = text

                articles.append({
                    "url": post["url"],
                    "title": title or post["title"],
                    "date": date_str,
                    "body_text": body_text,
                })
            except Exception as e:
                print(f"    ERROR: {e}")
                self.screenshot(f"substack_post_{i}_error")

        return articles


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="https://substack.com/@capitalwars")
    parser.add_argument("limit", nargs="?", type=int, default=5)
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    args = parser.parse_args()

    url = args.url
    limit = args.limit

    with SubstackAuthorReader(headless=args.headless) as reader:
        articles = reader.read_author_page(url, limit=limit)

    # Save output
    out_dir = SCRAPED_DIR / "substack_authors"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save individual articles
    for art in articles:
        slug = art["title"].lower().replace(" ", "-")[:50]
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        filepath = out_dir / f"{slug}.json"
        filepath.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")

    # Derive combined filename from URL (e.g. @capitalwars -> capitalwars_latest.txt)
    author_slug = url.rstrip("/").split("@")[-1].split("/")[-1].split(".")[0].lower()
    author_slug = "".join(c for c in author_slug if c.isalnum() or c in "-_") or "unknown"
    combined_path = out_dir / f"{author_slug}_latest.txt"

    # Save combined text for quick reading
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

    print(f"\n  Saved {len(articles)} articles to: {out_dir}")
    print(f"  Combined file: {combined_path}")
