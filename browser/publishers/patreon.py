"""
Patreon post publisher via Selenium + undetected-chromedriver.

Uses undetected-chromedriver to bypass Cloudflare bot detection.
Opens a browser where you log in manually once. Session persists.

Usage:
    python -m browser publish patreon [--dry-run] [--newsletter 1]
"""

import time
from pathlib import Path
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = PROJECT_ROOT / "browser" / "sessions"

NEWSLETTER_FILES = [
    "newsletter_1_trade_geopolitics.html",
    "newsletter_2_japan_equities.html",
    "newsletter_3_tech_macro.html",
]

PATREON_POSTS_URL = "https://www.patreon.com/posts"
PATREON_NEW_POST_URL = "https://www.patreon.com/posts/new"

TIER_PATTERNS = [
    "對沖基金經理分享",
    "學海無涯戰友群",
]


class PatreonPublisher:
    """Publish newsletters to Patreon via browser automation (Cloudflare-proof)."""

    def __init__(self, dry_run=False, newsletters=None, headless=False, draft=False):
        self.dry_run = dry_run
        self.draft = draft
        self.headless = headless
        self.output_dir = PROJECT_ROOT / "output"
        self.newsletter_files = newsletters or NEWSLETTER_FILES
        self.session_dir = SESSIONS_DIR / "patreon"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.driver = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()

    def start(self):
        """Launch undetected Chrome."""
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.session_dir}")

        if self.headless:
            options.add_argument("--headless=new")

        # Disable automation flags
        options.add_argument("--disable-blink-features=AutomationControlled")

        self.driver = uc.Chrome(options=options, use_subprocess=True)
        self.driver.set_window_size(1280, 900)
        print("  Browser started (undetected mode)")
        return self.driver

    def close(self):
        """Close browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def wait_for_user(self, message="Complete the action, then press Enter..."):
        """Pause for manual user action."""
        print(f"\n{'='*60}")
        print(f"  MANUAL ACTION REQUIRED")
        print(f"  {message}")
        print(f"{'='*60}")
        input("  Press ENTER when done >>> ")
        print()

    def screenshot(self, name="debug"):
        """Save screenshot."""
        path = PROJECT_ROOT / f"debug_patreon_{name}.png"
        if self.driver:
            self.driver.save_screenshot(str(path))
            print(f"  Screenshot: {path}")

    # ── Login ────────────────────────────────────────────────

    def is_logged_in(self) -> bool:
        """Check if already logged into Patreon."""
        self.driver.get(PATREON_POSTS_URL)
        time.sleep(3)

        # Look for creator dashboard elements
        try:
            self.driver.find_element(By.XPATH, "//*[contains(@href, '/posts/new')]")
            return True
        except:
            return False

    def login(self):
        """Manual login."""
        self.driver.get("https://www.patreon.com/login")
        time.sleep(2)

        self.wait_for_user(
            "Log in to Patreon in the browser.\n"
            "  Your session will be saved for future runs."
        )

    def ensure_logged_in(self):
        """Check login state and login if needed."""
        if not self.is_logged_in():
            print("  Not logged in. Please log in manually...")
            self.login()
        else:
            print("  Already logged in to Patreon.")

    # ── HTML Extraction ──────────────────────────────────────

    def extract_content_from_html(self, html_path: Path) -> dict:
        """Parse newsletter HTML into title + plain text."""
        html = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        title = ""
        title_el = soup.find("title")
        if title_el:
            title = title_el.get_text(strip=True)

        lines = []

        # Subtitle
        sub = soup.select_one(".subtitle")
        if sub:
            lines.append(sub.get_text(strip=True))

        # Issue badge
        badge = soup.select_one(".issue-badge")
        if badge:
            lines.append(badge.get_text(strip=True))
            lines.append("")

        # Sections
        for section in soup.select(".section"):
            h2 = section.find("h2")
            if h2:
                lines.append("")
                lines.append(f"**{h2.get_text(strip=True)}**")
                lines.append("")

            # Stat grids
            for grid in section.select(".stat-grid"):
                parts = []
                for stat in grid.select(".stat"):
                    val = stat.select_one(".val")
                    lbl = stat.select_one(".lbl")
                    if val and lbl:
                        parts.append(f"{val.get_text(strip=True)} — {lbl.get_text(' ', strip=True)}")
                if parts:
                    lines.append(" | ".join(parts))
                    lines.append("")

            # Articles
            for article in section.select(".article"):
                art_title = article.select_one(".article-title")
                if art_title:
                    lines.append(f"**{art_title.get_text(strip=True)}**")

                for p in article.find_all("p", recursive=False):
                    txt = p.get_text(strip=True)
                    if txt:
                        lines.append(txt)

                for dp in article.select(".data-point"):
                    lines.append(dp.get_text(" ", strip=True))

                for impl in article.select(".implication"):
                    label = impl.select_one(".label")
                    label_text = label.get_text(strip=True) if label else "投資啟示"
                    impl_text = impl.get_text(strip=True)
                    if label_text in impl_text:
                        impl_text = impl_text.replace(label_text, "", 1).strip()
                    lines.append(f"**[{label_text}]**")
                    lines.append(impl_text)

                lines.append("")

            # BofA box
            for bofa in section.select(".bofa-box"):
                h3 = bofa.find("h3")
                if h3:
                    lines.append(f"**{h3.get_text(strip=True)}**")
                for p in bofa.find_all("p"):
                    txt = p.get_text(strip=True)
                    if txt:
                        lines.append(txt)
                lines.append("")

            # Flow grids
            for flow_grid in section.select(".flow-grid"):
                for item in flow_grid.select(".flow-item"):
                    fl = item.select_one(".flow-label")
                    fv = item.select_one(".flow-val")
                    if fl and fv:
                        lines.append(f"  {fl.get_text(strip=True)}: {fv.get_text(strip=True)}")
                lines.append("")

            # VS table
            for table in section.select(".vs-table"):
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                    if cells:
                        lines.append(" | ".join(cells))
                lines.append("")

        # Callout
        callout = soup.select_one(".callout")
        if callout:
            ct = callout.select_one(".callout-title")
            if ct:
                lines.append("")
                lines.append(f"**{ct.get_text(strip=True)}**")
            for li in callout.select("li"):
                lines.append(f"• {li.get_text(strip=True)}")
            lines.append("")

        # Footer
        footer = soup.select_one(".footer")
        if footer:
            lines.append("")
            lines.append(footer.get_text(" | ", strip=True))

        content = "\n".join(lines)
        return {"title": title, "content": content}

    # ── Post Creation ────────────────────────────────────────

    def create_post(self, title: str, content: str) -> bool:
        """Create a Patreon post."""
        self.driver.get(PATREON_NEW_POST_URL)
        time.sleep(4)

        # Handle post type modal
        try:
            text_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Text')]"))
            )
            text_btn.click()
            time.sleep(2)
        except:
            pass

        # Fill title
        try:
            title_input = self.driver.find_element(By.XPATH, "//input[contains(@placeholder, 'Title')]")
            title_input.clear()
            title_input.send_keys(title)
            print(f"    Title: {title}")
        except Exception as e:
            print(f"    WARNING: Could not fill title: {e}")

        time.sleep(1)

        # Fill content
        try:
            editor = self.driver.find_element(By.XPATH, "//div[@contenteditable='true']")
            editor.click()
            time.sleep(0.5)
            editor.send_keys(content)
            print(f"    Content: {len(content)} chars")
        except Exception as e:
            print(f"    WARNING: Could not fill content: {e}")
            self.screenshot("editor_error")

        time.sleep(2)

        # Tier selection
        print(f"    Target tiers: {', '.join(TIER_PATTERNS)}")
        self.screenshot("before_tier_selection")
        self.wait_for_user(
            f"Select the tiers in the browser:\n"
            f"  {', '.join(TIER_PATTERNS)}\n"
            f"Then press Enter."
        )

        # Dry-run: stop here
        if self.dry_run:
            self.screenshot("dry_run_preview")
            print("    [DRY RUN] Post ready but NOT published.")
            self.wait_for_user("Review the post, then press Enter.")
            return True

        # Draft mode: save as draft
        if self.draft:
            self.screenshot("draft_preview")
            self.wait_for_user(
                "Click 'Save as draft' in the browser (NOT Publish).\n"
                "  Then press Enter when done."
            )
            print("    Saved as draft (manual confirmation)")
            return True

        # Publish mode
        self.wait_for_user("Click 'Publish' in the browser, then press Enter when done.")
        print("    Published (manual confirmation)")
        return True

    # ── Main ─────────────────────────────────────────────────

    def run(self):
        if self.dry_run:
            mode = "DRY RUN"
        elif self.draft:
            mode = "DRAFT"
        else:
            mode = "LIVE"
        print(f"\n{'='*50}")
        print(f"  Patreon Publisher — Selenium ({mode})")
        print(f"  Target tiers: {', '.join(TIER_PATTERNS)}")
        print(f"  Newsletters: {len(self.newsletter_files)}")
        print(f"{'='*50}\n")

        self.ensure_logged_in()

        results = []
        for i, filename in enumerate(self.newsletter_files, 1):
            filepath = self.output_dir / filename
            if not filepath.exists():
                print(f"  [{i}/{len(self.newsletter_files)}] SKIP: {filename}")
                results.append((filename, "skipped"))
                continue

            print(f"\n  [{i}/{len(self.newsletter_files)}] {filename}")

            try:
                data = self.extract_content_from_html(filepath)
                print(f"    Title: {data['title']}")
                print(f"    Content: {len(data['content'])} chars")

                ok = self.create_post(data["title"], data["content"])
                results.append((filename, "published" if ok else "failed"))

                if i < len(self.newsletter_files):
                    time.sleep(2)

            except Exception as e:
                print(f"    ERROR: {e}")
                self.screenshot(f"error_{i}")
                results.append((filename, f"error: {e}"))

        print(f"\n{'='*50}")
        print("  Results:")
        for fname, status in results:
            print(f"    {status.upper():12s} {fname}")
        print(f"{'='*50}")
