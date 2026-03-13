"""
Substack article scraper.

Logs in to Substack and scrapes articles from the user's inbox
(subscribed newsletters from other authors).
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from browser.base import BrowserAutomation, SCRAPED_DIR


class SubstackScraper(BrowserAutomation):
    SERVICE_NAME = "substack"
    SIGN_IN_URL = "https://substack.com/sign-in"
    INBOX_URL = "https://substack.com/inbox"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.output_dir = SCRAPED_DIR / "substack"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_logged_in(self) -> bool:
        self.page.goto(self.INBOX_URL, wait_until="networkidle")
        self.page.wait_for_timeout(3000)
        return "sign-in" not in self.page.url and "inbox" in self.page.url

    def login(self):
        self.page.goto(self.SIGN_IN_URL, wait_until="networkidle")
        self.page.wait_for_timeout(2000)

        email = os.getenv("SUBSTACK_EMAIL", "")
        password = os.getenv("SUBSTACK_PASSWORD", "")

        if email and password:
            # Try password login path
            pwd_link = self.page.locator('text=Sign in with password')
            if pwd_link.count() > 0:
                pwd_link.click()
                self.page.wait_for_timeout(1000)

            email_input = self.page.locator('input[type="email"], input[name="email"]').first
            if email_input.count() > 0:
                email_input.fill(email)

            pwd_input = self.page.locator('input[type="password"]').first
            if pwd_input.count() > 0:
                pwd_input.fill(password)

            submit = self.page.locator('button[type="submit"], button:has-text("Sign in")').first
            if submit.count() > 0:
                submit.click()

            self.page.wait_for_timeout(3000)

            # Check for 2FA
            twofa = self.page.locator('input[name="code"], input[placeholder*="code"]')
            if twofa.count() > 0:
                self.wait_for_user("Enter your Substack 2FA code in the browser.")
        else:
            self.wait_for_user(
                "Log in to Substack in the browser.\n"
                "  Tip: Set SUBSTACK_EMAIL and SUBSTACK_PASSWORD in .env for auto-fill."
            )

    def scrape_article_list(self, limit: int = 10) -> list[dict]:
        """Get list of recent articles from inbox."""
        self.page.goto(self.INBOX_URL, wait_until="networkidle")
        self.page.wait_for_timeout(3000)

        articles = []
        article_links = self.page.locator('a[href*="/p/"]')
        count = min(article_links.count(), limit)

        for i in range(count):
            link = article_links.nth(i)
            href = link.get_attribute("href") or ""
            title_el = link.locator("h2, h3").first
            title = title_el.inner_text() if title_el.count() > 0 else ""

            if href and "/p/" in href:
                full_url = href if href.startswith("http") else f"https://substack.com{href}"
                articles.append({"url": full_url, "title": title.strip()})

        return articles

    def scrape_article_content(self, url: str) -> dict:
        """Navigate to an article and extract its content."""
        self.page.goto(url, wait_until="networkidle")
        self.page.wait_for_timeout(2000)

        title = ""
        title_el = self.page.locator("h1").first
        if title_el.count() > 0:
            title = title_el.inner_text().strip()

        author = ""
        author_el = self.page.locator('[class*="author-name"], [class*="byline"]').first
        if author_el.count() > 0:
            author = author_el.inner_text().strip()

        date_str = ""
        date_el = self.page.locator("time, [datetime]").first
        if date_el.count() > 0:
            date_str = date_el.get_attribute("datetime") or date_el.inner_text()

        body_el = self.page.locator('[class*="body"], article, .post-content').first
        body_html = body_el.inner_html() if body_el.count() > 0 else ""
        body_text = body_el.inner_text() if body_el.count() > 0 else ""

        newsletter = ""
        nl_el = self.page.locator('[class*="publication-name"], [class*="pub-name"]').first
        if nl_el.count() > 0:
            newsletter = nl_el.inner_text().strip()

        hkt = timezone(timedelta(hours=8))
        return {
            "source": "substack",
            "scraped_at": datetime.now(hkt).isoformat(),
            "url": url,
            "title": title,
            "author": author,
            "published_date": date_str,
            "content_type": "article",
            "summary": body_text[:500] if body_text else "",
            "body_text": body_text,
            "body_html": body_html,
            "metadata": {"newsletter_name": newsletter},
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
        print(f"  Substack Scraper (limit: {limit})")
        print(f"{'='*50}\n")

        self.ensure_logged_in()
        articles = self.scrape_article_list(limit=limit)
        print(f"  Found {len(articles)} articles in inbox\n")

        for i, meta in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {meta['title'][:60]}")
            try:
                article = self.scrape_article_content(meta["url"])
                self.save_article(article)
            except Exception as e:
                print(f"    ERROR: {e}")
                self.screenshot(f"article_{i}_error")

        print(f"\n  Done. Files saved to: {self.output_dir}")
