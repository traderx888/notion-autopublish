"""
Institutional insights scraper.

Scrapes public market research pages from Goldman Sachs, Citadel Securities,
and Morgan Stanley using stealth headless Playwright with headed fallback.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from browser.base import BrowserAutomation, SCRAPED_DIR

OUTPUT_DIR = SCRAPED_DIR / "institutional"

# Bot-check detection strings (Akamai, Imperva, Cloudflare, generic)
_BOT_CHECK_SIGNALS = [
    "just a moment",
    "checking your browser",
    "please wait",
    "verify you are human",
    "access denied",
    "enable javascript and cookies",
    "performing security verification",
    "one more step",
    "attention required",
    "pardon our interruption",
]

INSTITUTIONAL_SITES: Dict[str, Dict[str, Any]] = {
    "goldmansachs": {
        "name": "Goldman Sachs",
        "listing_url": "https://www.goldmansachs.com/insights/the-markets",
        "base_url": "https://www.goldmansachs.com",
        "article_link_selectors": [
            'a[href*="/insights/the-markets/"]',
            'a[href*="/insights/articles/"]',
        ],
        "title_selectors": ["h1"],
        "body_selectors": [
            "#__next",   # React SPA root — GS uses Next.js
            "main",
            "article",
            '[role="main"]',
        ],
        "date_selectors": [
            "time[datetime]",
            '[class*="date"]',
        ],
        "spa_wait": 8000,  # GS needs extra time for React hydration
    },
    "citadelsecurities": {
        "name": "Citadel Securities",
        "listing_url": "https://www.citadelsecurities.com/news-and-insights/category/market-insights/",
        "base_url": "https://www.citadelsecurities.com",
        "listing_is_content": True,  # Listing page itself has the summaries
        "article_link_selectors": [
            'a[href*="/news-and-insights/series/"]',
            'a[href*="/news-and-insights/"]',
        ],
        "title_selectors": ["h1", "h2"],
        "body_selectors": [
            "main",
            '[role="main"]',
            ".entry-content",
            "article",
        ],
        "date_selectors": [
            "time[datetime]",
            '[class*="date"]',
        ],
    },
    "morganstanley": {
        "name": "Morgan Stanley",
        "listing_url": "https://www.morganstanley.com/insights/topics/market-trends",
        "base_url": "https://www.morganstanley.com",
        "article_link_selectors": [
            'a[href*="/insights/articles/"]',
            'a[href*="/ideas/"]',
        ],
        "title_selectors": ["h1"],
        "body_selectors": [
            "main",
            "article",
            '[role="main"]',
        ],
        "date_selectors": [
            "time[datetime]",
            '[class*="date"]',
        ],
    },
}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _is_bot_check_page(body_text: str) -> bool:
    """Detect Akamai / Imperva / Cloudflare challenge pages."""
    lowered = (body_text or "").strip().lower()
    return any(sig in lowered for sig in _BOT_CHECK_SIGNALS) and len(lowered) < 2000


def _slugify(text: str, max_len: int = 60) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:max_len]


class InstitutionalInsightsScraper(BrowserAutomation):
    """Scraper for public institutional research pages."""

    SERVICE_NAME = "institutional"
    USE_CHROME_PROFILE = False  # Public pages — no login needed

    def __init__(self, headless: bool = True, use_chrome: bool | None = None,
                 slow_mo: int = 150):
        super().__init__(headless=headless, slow_mo=slow_mo, use_chrome=use_chrome)
        self._headed_fallback_used = False

    # ------------------------------------------------------------------
    # Browser launch — prefer real Chrome channel for TLS fingerprint
    # ------------------------------------------------------------------

    def start(self):
        """Launch with Chrome channel preference and stealth flags."""
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        launch_kwargs = dict(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 1000},
            locale="en-US",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        # Prefer real Chrome for better TLS fingerprint (JA3)
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
        except Exception:
            self.context = self.playwright.chromium.launch_persistent_context(
                **launch_kwargs,
            )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

        # Patch navigator.webdriver to false
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
        """)
        return self.page

    def is_logged_in(self) -> bool:
        return True  # Public pages — no login needed

    def login(self):
        pass  # No login needed

    # ------------------------------------------------------------------
    # Anti-bot handling
    # ------------------------------------------------------------------

    def _navigate(self, url: str, retries: int = 2, spa_wait: int = 5000) -> bool:
        """Navigate to URL with domcontentloaded + bot-check wait."""
        for attempt in range(1, retries + 1):
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self.page.wait_for_timeout(spa_wait)

                if self._wait_for_bot_check(timeout_seconds=20):
                    return True

                if attempt < retries:
                    print(f"    Bot check not cleared, retrying ({attempt}/{retries})...")
                    self.page.wait_for_timeout(5000)
            except Exception as e:
                print(f"    Navigation error (attempt {attempt}): {e}")
                if attempt < retries:
                    self.page.wait_for_timeout(3000)

        return False

    def _wait_for_bot_check(self, timeout_seconds: int = 20) -> bool:
        """Wait for bot-check page to clear. Returns True if clear."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            body_text = self._body_text()
            if not _is_bot_check_page(body_text):
                return True
            self.page.wait_for_timeout(2000)
        return not _is_bot_check_page(self._body_text())

    def _body_text(self) -> str:
        """Get current page body text."""
        try:
            return self.page.inner_text("body")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Content extraction
    # ------------------------------------------------------------------

    def _extract_article_links(self, site_config: Dict, limit: int) -> List[Dict]:
        """Extract article links from the listing page."""
        links = []
        seen_urls = set()

        for selector in site_config["article_link_selectors"]:
            try:
                elements = self.page.locator(selector)
                count = elements.count()
                for i in range(count):
                    el = elements.nth(i)
                    href = el.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue

                    # Resolve relative URLs
                    if href.startswith("/"):
                        href = site_config["base_url"] + href

                    # Skip non-article links (# anchors, javascript, etc.)
                    if not href.startswith("http"):
                        continue

                    # Skip listing page itself
                    if href.rstrip("/") == site_config["listing_url"].rstrip("/"):
                        continue

                    seen_urls.add(href)

                    # Try to get title text
                    title = ""
                    try:
                        title = el.inner_text().strip()[:200]
                    except Exception:
                        pass

                    # Filter out navigation-only links (too short to be article titles)
                    if title and len(title) > 5:
                        links.append({"url": href, "title": title})

                    if len(links) >= limit:
                        break
            except Exception:
                continue

            if len(links) >= limit:
                break

        return links

    def _extract_article_content(self, url: str, site_config: Dict) -> Dict:
        """Navigate to an article and extract its full content."""
        result = {
            "url": url,
            "title": "",
            "date": "",
            "body_text": "",
            "scraped_at": _now_iso(),
        }

        spa_wait = site_config.get("spa_wait", 5000)
        if not self._navigate(url, spa_wait=spa_wait):
            result["error"] = "navigation_failed"
            return result

        # Extract title
        for selector in site_config["title_selectors"]:
            try:
                el = self.page.locator(selector).first
                if el.count() > 0:
                    result["title"] = el.inner_text().strip()
                    break
            except Exception:
                continue

        # Extract date — validate it looks like a date
        _date_pattern = re.compile(
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})",
            re.IGNORECASE,
        )
        for selector in site_config["date_selectors"]:
            try:
                el = self.page.locator(selector).first
                if el.count() > 0:
                    dt = el.get_attribute("datetime")
                    if dt:
                        result["date"] = dt
                    else:
                        text = el.inner_text().strip()
                        if _date_pattern.search(text) and len(text) < 60:
                            result["date"] = text
                    if result["date"]:
                        break
            except Exception:
                continue

        # Extract body — pick the longest match
        best_body = ""
        for selector in site_config["body_selectors"]:
            try:
                el = self.page.locator(selector).first
                if el.count() > 0:
                    text = el.inner_text().strip()
                    if len(text) > len(best_body):
                        best_body = text
            except Exception:
                continue

        result["body_text"] = best_body
        return result

    # ------------------------------------------------------------------
    # Per-site scraping
    # ------------------------------------------------------------------

    def scrape_site(self, site_key: str, limit: int = 5) -> List[Dict]:
        """Scrape articles from a single institutional site."""
        site_config = INSTITUTIONAL_SITES.get(site_key)
        if not site_config:
            print(f"  [institutional] Unknown site: {site_key}")
            return []

        print(f"\n  {'=' * 50}")
        print(f"  Scraping {site_config['name']} (limit={limit})")
        print(f"  {'=' * 50}")

        # Navigate to listing page
        spa_wait = site_config.get("spa_wait", 5000)
        print(f"  Navigating to: {site_config['listing_url']}")
        if not self._navigate(site_config["listing_url"], spa_wait=spa_wait):
            print(f"  BLOCKED by bot protection. ", end="")
            if self.headless and not self._headed_fallback_used:
                print("Will retry in headed mode later.")
                return [{"error": "bot_blocked", "site": site_key}]
            print("Skipping.")
            self.screenshot(f"blocked_{site_key}")
            return []

        # Scroll down to load more content
        for _ in range(3):
            self.page.evaluate("window.scrollBy(0, window.innerHeight)")
            self.page.wait_for_timeout(1500)

        # For sites where the listing page IS the content (e.g. Citadel
        # market-insights shows article summaries inline), extract directly.
        if site_config.get("listing_is_content"):
            body_text = self._body_text()
            if body_text and len(body_text) > 200:
                print(f"  Extracted listing page ({len(body_text)} chars)")
                return [{
                    "url": site_config["listing_url"],
                    "title": f"{site_config['name']} - Market Insights",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "body_text": body_text[:50000],
                    "scraped_at": _now_iso(),
                }]

        # Extract article links
        article_links = self._extract_article_links(site_config, limit)

        # Deduplicate by URL
        seen = set()
        deduped = []
        for link in article_links:
            url_norm = link["url"].rstrip("/")
            if url_norm not in seen:
                seen.add(url_norm)
                deduped.append(link)
        article_links = deduped
        print(f"  Found {len(article_links)} articles")

        if not article_links:
            # Fallback: grab text from the listing page itself
            print("  No article links found, extracting listing page content...")
            body_text = self._body_text()
            if body_text and len(body_text) > 200:
                return [{
                    "url": site_config["listing_url"],
                    "title": f"{site_config['name']} - Market Insights (listing)",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "body_text": body_text[:50000],
                    "scraped_at": _now_iso(),
                }]
            self.screenshot(f"no_articles_{site_key}")
            return []

        # Scrape each article
        articles = []
        for i, link in enumerate(article_links, 1):
            print(f"  [{i}/{len(article_links)}] {link['title'][:60]}")
            try:
                article = self._extract_article_content(link["url"], site_config)
                if not article.get("title"):
                    article["title"] = link["title"]
                articles.append(article)
                # Human-like delay between articles
                self.page.wait_for_timeout(2000 + (i % 3) * 1000)
            except Exception as e:
                print(f"    ERROR: {e}")
                self.screenshot(f"article_error_{site_key}_{i}")

        return articles

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _save_site_output(self, site_key: str, articles: List[Dict]) -> Optional[Path]:
        """Save scraped articles to disk."""
        if not articles:
            return None

        site_dir = OUTPUT_DIR / site_key
        site_dir.mkdir(parents=True, exist_ok=True)

        # Save individual article JSON files
        for art in articles:
            if art.get("error"):
                continue
            slug = _slugify(art.get("title", "untitled"))
            filepath = site_dir / f"{slug}.json"
            filepath.write_text(
                json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        # Save combined text file
        combined = []
        for art in articles:
            if art.get("error"):
                continue
            combined.append(f"{'=' * 60}")
            combined.append(f"TITLE: {art.get('title', '')}")
            combined.append(f"DATE: {art.get('date', '')}")
            combined.append(f"URL: {art.get('url', '')}")
            combined.append(f"{'=' * 60}")
            combined.append(art.get("body_text", ""))
            combined.append("")

        combined_path = OUTPUT_DIR / f"{site_key}_latest.txt"
        combined_path.write_text("\n".join(combined), encoding="utf-8")
        print(f"  Saved {len(articles)} articles to: {combined_path}")
        return combined_path

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run(
        self,
        site_keys: Optional[List[str]] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Scrape all (or selected) institutional sites."""
        keys = site_keys or list(INSTITUTIONAL_SITES.keys())
        results: Dict[str, Any] = {}
        needs_headed_retry: List[str] = []

        print(f"\n{'=' * 50}")
        print(f"  Institutional Insights Scraper")
        print(f"  Sites: {', '.join(keys)} | Limit: {limit}")
        print(f"  Mode: {'headless' if self.headless else 'headed'}")
        print(f"{'=' * 50}")

        for key in keys:
            articles = self.scrape_site(key, limit=limit)

            # Check if bot-blocked and needs headed retry
            if articles and articles[0].get("error") == "bot_blocked":
                needs_headed_retry.append(key)
                continue

            path = self._save_site_output(key, articles)
            results[key] = {
                "success": bool(articles),
                "article_count": len([a for a in articles if not a.get("error")]),
                "output_path": str(path) if path else None,
            }

        # Headed fallback for blocked sites
        if needs_headed_retry and self.headless:
            print(f"\n  Retrying {len(needs_headed_retry)} blocked site(s) in headed mode...")
            self._headed_fallback_used = True
            self.close()
            self.headless = False
            self.start()
            for key in needs_headed_retry:
                articles = self.scrape_site(key, limit=limit)
                path = self._save_site_output(key, articles)
                results[key] = {
                    "success": bool(articles),
                    "article_count": len([a for a in articles if not a.get("error")]),
                    "output_path": str(path) if path else None,
                    "headed_fallback": True,
                }

        # Write manifest
        manifest = {
            "generated_at": _now_iso(),
            "site_count": len(results),
            "success_count": sum(1 for r in results.values() if r.get("success")),
            "sites": results,
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = OUTPUT_DIR / "institutional_latest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"\n  Done: {manifest['success_count']}/{manifest['site_count']} sites scraped")
        print(f"  Manifest: {manifest_path}")
        return manifest
