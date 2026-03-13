"""
Quick script to scrape a Seeking Alpha group/chat page
using the existing persistent browser session.
"""

from browser.base import BrowserAutomation


class SAGroupReader(BrowserAutomation):
    SERVICE_NAME = "seekingalpha"
    USE_CHROME_PROFILE = False  # reuse existing session dir, no need to copy from Chrome

    def is_logged_in(self) -> bool:
        return True  # assume logged in from existing session

    def login(self):
        pass

    def read_group_page(self, url: str) -> str:
        print(f"  Navigating to: {url}")
        self.page.goto(url, wait_until="networkidle")
        self.page.wait_for_timeout(5000)

        # Scroll down to load more content
        for _ in range(3):
            self.page.evaluate("window.scrollBy(0, 800)")
            self.page.wait_for_timeout(1500)

        # Try to extract post/message content
        # SA group pages typically have post cards or message blocks
        posts = []

        # Try common selectors for group posts
        selectors = [
            'article', '[data-test-id="post"]', '[class*="post"]',
            '[class*="message"]', '[class*="comment"]', '[class*="card"]',
            '.feed-item', '[class*="feed"]', '[class*="content-block"]',
        ]

        for sel in selectors:
            elements = self.page.locator(sel)
            count = elements.count()
            if count > 0:
                print(f"  Found {count} elements with selector: {sel}")
                for i in range(min(count, 30)):
                    text = elements.nth(i).inner_text().strip()
                    if text and len(text) > 20:
                        posts.append(text)

        if not posts:
            # Fallback: grab main content area
            print("  No posts found via selectors, grabbing full page text...")
            body = self.page.locator("main, #content, [role='main'], body").first
            if body.count() > 0:
                posts.append(body.inner_text())

        # Take screenshot for reference
        self.screenshot("group_page")

        combined = "\n\n---\n\n".join(posts)
        print(f"\n  Extracted {len(posts)} content blocks ({len(combined)} chars)")
        return combined


SA_GROUPS = {
    "pam": {
        "url": "https://rc.seekingalpha.com/group/predictive-analytic-models",
        "output": "scraped_data/sa_group_predictive_models.txt",
    },
    "gamma-charm": {
        "url": "https://rc.seekingalpha.com/group/PAM_SPX-GAMMA-CHARM-SURFACE",
        "output": "scraped_data/sa_group_gamma_charm.txt",
    },
}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--group", default="pam", choices=list(SA_GROUPS.keys()),
                        help="SA group to scrape (default: pam)")
    parser.add_argument("--url", default=None, help="Custom group URL (overrides --group)")
    parser.add_argument("--output", default=None, help="Custom output path (overrides --group)")
    args = parser.parse_args()

    group = SA_GROUPS[args.group]
    url = args.url or group["url"]
    out_path = args.output or group["output"]

    with SAGroupReader(headless=args.headless) as reader:
        content = reader.read_group_page(url)

    # Save output
    from pathlib import Path
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"\n  Saved to: {out}")
    print(f"\n{'='*60}")
    print("  PREVIEW (first 2000 chars):")
    print(f"{'='*60}")
    print(content[:2000])
