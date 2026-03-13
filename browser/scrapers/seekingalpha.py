"""
Seeking Alpha article scraper.

Logs in to Seeking Alpha and scrapes premium articles
the user has access to via their subscription.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from browser.base import BrowserAutomation, SCRAPED_DIR


class SeekingAlphaScraper(BrowserAutomation):
    SERVICE_NAME = "seekingalpha"
    USE_CHROME_PROFILE = True  # Use real Chrome profile (Google SSO login)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.output_dir = SCRAPED_DIR / "seekingalpha"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_logged_in(self) -> bool:
        self.page.goto("https://seekingalpha.com/", wait_until="networkidle")
        self.page.wait_for_timeout(3000)
        # Check for user menu indicating logged-in state
        avatar = self.page.locator(
            '[data-test-id="user-nav"], [class*="avatar"], [class*="user-menu"]'
        )
        return avatar.count() > 0

    def login(self):
        self.page.goto(
            "https://seekingalpha.com/account/login", wait_until="networkidle"
        )
        self.page.wait_for_timeout(3000)

        # Handle Cloudflare challenge
        if "challenge" in self.page.url or "captcha" in self.page.content().lower():
            self.wait_for_user("Complete the CAPTCHA/Cloudflare challenge in the browser.")

        # Try clicking "Sign in with Google" button
        google_btn = self.page.locator(
            'button:has-text("Google"), a:has-text("Google"), '
            '[data-test-id="google-login"], [class*="google"]'
        ).first
        if google_btn.count() > 0:
            google_btn.click()
            self.page.wait_for_timeout(2000)

            # Google OAuth may open a popup — handle both popup and redirect flows
            if len(self.context.pages) > 1:
                # Popup flow: Google login opened in a new window
                google_page = self.context.pages[-1]
                google_page.bring_to_front()
                self.wait_for_user(
                    "Complete Google sign-in in the popup window.\n"
                    "  1. Select your Google account\n"
                    "  2. Enter password / complete 2FA if prompted\n"
                    "  3. The popup will close automatically when done"
                )
            else:
                # Redirect flow: same tab
                self.wait_for_user(
                    "Complete Google sign-in in the browser.\n"
                    "  1. Select your Google account\n"
                    "  2. Enter password / complete 2FA if prompted"
                )
        else:
            # Fallback: let user handle login manually
            self.wait_for_user(
                "Log in to Seeking Alpha in the browser.\n"
                "  Click 'Sign in with Google' and complete the login."
            )

        # Wait for redirect back to Seeking Alpha
        self.page.bring_to_front()
        self.page.wait_for_timeout(3000)

    def scrape_feed(self, limit: int = 10) -> list[dict]:
        """Get article URLs from latest articles page."""
        self.page.goto(
            "https://seekingalpha.com/latest-articles", wait_until="networkidle"
        )
        self.page.wait_for_timeout(3000)

        articles = []
        links = self.page.locator('a[href*="/article/"]')
        seen_urls = set()

        for i in range(links.count()):
            if len(articles) >= limit:
                break
            href = links.nth(i).get_attribute("href") or ""
            title = links.nth(i).inner_text().strip()
            full_url = (
                f"https://seekingalpha.com{href}" if href.startswith("/") else href
            )

            if full_url not in seen_urls and "/article/" in full_url and title:
                seen_urls.add(full_url)
                articles.append({"url": full_url, "title": title})

        return articles

    def scrape_article_content(self, url: str) -> dict:
        """Scrape a single article's content."""
        self.page.goto(url, wait_until="networkidle")
        self.page.wait_for_timeout(3000)

        # Check for paywall
        paywall = self.page.locator('[class*="paywall"], [data-test-id="paywall"]')
        if paywall.count() > 0:
            print("    (Paywalled -- Premium subscription may be needed)")

        title = ""
        if self.page.locator("h1").count() > 0:
            title = self.page.locator("h1").first.inner_text().strip()

        author = ""
        author_el = self.page.locator(
            '[data-test-id="author-name"], [class*="author"]'
        ).first
        if author_el.count() > 0:
            author = author_el.inner_text().strip()

        date_str = ""
        date_el = self.page.locator('time, [data-test-id="post-date"]').first
        if date_el.count() > 0:
            date_str = date_el.get_attribute("datetime") or date_el.inner_text()

        body_el = self.page.locator(
            '[data-test-id="article-body"], article .paywall-full-content, '
            '[class*="article-body"]'
        ).first
        body_text = body_el.inner_text() if body_el.count() > 0 else ""
        body_html = body_el.inner_html() if body_el.count() > 0 else ""

        # Extract tickers
        tickers = []
        ticker_els = self.page.locator('a[href*="/symbol/"]')
        for i in range(ticker_els.count()):
            ticker = ticker_els.nth(i).inner_text().strip()
            if ticker and len(ticker) <= 6:
                tickers.append(ticker)

        hkt = timezone(timedelta(hours=8))
        return {
            "source": "seekingalpha",
            "scraped_at": datetime.now(hkt).isoformat(),
            "url": url,
            "title": title,
            "author": author,
            "published_date": date_str,
            "content_type": "article",
            "tags": list(set(tickers)),
            "summary": body_text[:500],
            "body_text": body_text,
            "body_html": body_html,
            "metadata": {"tickers": list(set(tickers))},
        }

    def save_article(self, article: dict):
        slug = re.sub(r"[^\w\-]", "", article["title"].lower().replace(" ", "-"))[:60]
        date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date}_{slug}.json"
        filepath = self.output_dir / filename
        filepath.write_text(
            json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"    Saved: {filepath.name}")

    def run(self, limit: int = 10):
        print(f"\n{'='*50}")
        print(f"  Seeking Alpha Scraper (limit: {limit})")
        print(f"{'='*50}\n")

        self.ensure_logged_in()
        articles = self.scrape_feed(limit=limit)
        print(f"  Found {len(articles)} articles\n")

        for i, meta in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {meta['title'][:60]}")
            try:
                article = self.scrape_article_content(meta["url"])
                self.save_article(article)
            except Exception as e:
                print(f"    ERROR: {e}")
                self.screenshot(f"article_{i}_error")

        print(f"\n  Done. Files saved to: {self.output_dir}")
