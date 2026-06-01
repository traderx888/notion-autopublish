"""LinkedIn content discovery -- find relevant posts to comment on.

Uses BrowserAutomation to scroll the LinkedIn feed and extract posts
matching brand-relevant topics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HKT = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class DiscoveryResult:
    url: str
    title: str
    author: str
    content_snippet: str
    engagement: dict
    relevance_score: float
    platform: str
    discovered_at: str


def _score_relevance(text: str, config: dict) -> float:
    """Score how relevant a post is to brand topics."""
    keywords = (
        config["seo"]["target_keywords_en"] +
        config["seo"]["target_keywords_zh"] +
        config["topics"]["primary"] +
        config["topics"]["secondary"]
    )
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower().replace("_", " ") in text_lower)
    return min(matches / 5.0, 1.0)


class LinkedInDiscovery:
    """Discover relevant LinkedIn posts via browser feed scrolling."""

    def __init__(self, headless: bool = False):
        from browser.base import BrowserAutomation

        class _LinkedInBrowser(BrowserAutomation):
            SERVICE_NAME = "linkedin_brand"
            USE_CHROME_PROFILE = True

            def is_logged_in(self) -> bool:
                self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                self.page.wait_for_timeout(3000)
                return self.page.locator(".feed-shared-update-v2").count() > 0

            def login(self):
                self.page.goto("https://www.linkedin.com/login")
                self.wait_for_user("Please log in to LinkedIn, then press Enter.")

        self._browser = _LinkedInBrowser(headless=headless)

    def __enter__(self):
        self._browser.start()
        self._browser.ensure_logged_in()
        return self

    def __exit__(self, *args):
        self._browser.__exit__(*args)

    def discover(self, config: dict, limit: int = 10) -> list[DiscoveryResult]:
        """Scroll feed and extract relevant posts."""
        page = self._browser.page
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        results = []
        seen_urls = set()

        # Scroll and collect posts
        for scroll_round in range(5):
            posts = page.locator(".feed-shared-update-v2").all()

            for post in posts:
                try:
                    # Extract post URL
                    link_el = post.locator("a[href*='/posts/'], a[href*='/pulse/']").first
                    if link_el.count() == 0:
                        continue
                    url = link_el.get_attribute("href") or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Extract author
                    author_el = post.locator(".update-components-actor__name").first
                    author = author_el.inner_text() if author_el.count() > 0 else "Unknown"

                    # Extract content
                    content_el = post.locator(".feed-shared-update-v2__description, .update-components-text").first
                    snippet = content_el.inner_text()[:500] if content_el.count() > 0 else ""

                    # Score relevance
                    score = _score_relevance(snippet + " " + author, config)
                    if score < 0.2:
                        continue

                    results.append(DiscoveryResult(
                        url=url,
                        title=snippet[:80],
                        author=author.strip(),
                        content_snippet=snippet,
                        engagement={},
                        relevance_score=round(score, 2),
                        platform="linkedin",
                        discovered_at=datetime.now(HKT).isoformat(),
                    ))

                except Exception:
                    continue

            if len(results) >= limit:
                break

            # Scroll down
            page.evaluate("window.scrollBy(0, 1500)")
            page.wait_for_timeout(2000)

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]


def discover_from_search(query: str, config: dict, limit: int = 10) -> list[DiscoveryResult]:
    """Discover posts via LinkedIn search (requires browser session)."""
    # This is a convenience wrapper for CLI use
    with LinkedInDiscovery() as ld:
        # Override: navigate to search instead of feed
        page = ld._browser.page
        encoded = query.replace(" ", "%20")
        page.goto(
            f"https://www.linkedin.com/search/results/content/?keywords={encoded}",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(3000)
        return ld.discover(config, limit)
