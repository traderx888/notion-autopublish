"""
Shared Playwright automation base class.

Provides persistent browser sessions, manual intervention prompts,
and error handling for all grabbers and scrapers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext, Page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = PROJECT_ROOT / "browser" / "sessions"
SCRAPED_DIR = PROJECT_ROOT / "scraped_data"

# Standard Chrome user data directory on Windows
CHROME_USER_DATA = Path(os.environ.get(
    "CHROME_USER_DATA",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
))

# Files to copy from Chrome profile to preserve login sessions
_CHROME_SESSION_FILES = [
    "Cookies",
    "Cookies-journal",
    "Login Data",
    "Login Data-journal",
    "Web Data",
    "Web Data-journal",
    "Preferences",
    "Secure Preferences",
]
_CHROME_SESSION_DIRS = [
    "Local Storage",
    "Session Storage",
    "IndexedDB",
]


def is_chrome_running() -> bool:
    """Check if Google Chrome is currently running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
            capture_output=True, text=True, timeout=5,
        )
        return "chrome.exe" in result.stdout.lower()
    except Exception:
        return False


def copy_chrome_session(dest_dir: Path, profile: str = "Default") -> None:
    """
    Copy Chrome's login/session data into a Playwright-compatible directory.

    Copies cookies, localStorage, and session files from the real Chrome
    profile so Playwright's Chromium can reuse existing logins (Google SSO, etc).
    Chrome must be closed first (files are locked while Chrome runs).
    """
    chrome_profile = CHROME_USER_DATA / profile
    if not chrome_profile.exists():
        print(f"  WARNING: Chrome profile not found at {chrome_profile}")
        return

    dest_profile = dest_dir / profile
    dest_profile.mkdir(parents=True, exist_ok=True)

    # Copy Local State (contains cookie encryption key) to the user data root
    local_state = CHROME_USER_DATA / "Local State"
    if local_state.exists():
        shutil.copy2(str(local_state), str(dest_dir / "Local State"))

    # Copy session files
    for filename in _CHROME_SESSION_FILES:
        src = chrome_profile / filename
        if src.exists():
            shutil.copy2(str(src), str(dest_profile / filename))

    # Copy session directories
    for dirname in _CHROME_SESSION_DIRS:
        src = chrome_profile / dirname
        dst = dest_profile / dirname
        if src.exists():
            if dst.exists():
                shutil.rmtree(str(dst))
            shutil.copytree(str(src), str(dst))

    print(f"  Chrome session copied to: {dest_dir.name}")


class BrowserAutomation:
    """Base class for all browser automation tasks."""

    SERVICE_NAME: str = "default"
    # Set to True in subclass to use cookies from the real Chrome profile
    USE_CHROME_PROFILE: bool = False

    def __init__(self, headless: bool = False, slow_mo: int = 100,
                 use_chrome: bool | None = None):
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        # CLI flag overrides class default
        if use_chrome is not None:
            self.USE_CHROME_PROFILE = use_chrome

    @property
    def session_dir(self) -> Path:
        """Per-service persistent browser profile directory."""
        d = SESSIONS_DIR / self.SERVICE_NAME
        d.mkdir(parents=True, exist_ok=True)
        return d

    def start(self) -> Page:
        """Launch browser with persistent context. Returns the active page."""
        if self.USE_CHROME_PROFILE:
            if is_chrome_running():
                print("\n" + "=" * 60)
                print("  Chrome is currently running.")
                print("  Please CLOSE ALL Chrome windows first,")
                print("  then press Enter to continue.")
                print("  (Need to copy session while Chrome is closed)")
                print("=" * 60)
                input("  Press ENTER when Chrome is closed >>> ")
                print()

            print("  Copying Chrome session data...")
            copy_chrome_session(self.session_dir)

        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self.page

    def wait_for_user(self, message: str = "Complete manual step, then press Enter..."):
        """Pause automation for manual user action in the browser."""
        print(f"\n{'='*60}")
        print(f"  MANUAL ACTION REQUIRED")
        print(f"  {message}")
        print(f"{'='*60}")
        input("  Press ENTER when done >>> ")
        print()

    def is_logged_in(self) -> bool:
        """Subclasses override to check if session is authenticated."""
        raise NotImplementedError

    def login(self):
        """Subclasses override with site-specific login flow."""
        raise NotImplementedError

    def ensure_logged_in(self):
        """Check session; login if needed."""
        if not self.is_logged_in():
            print(f"[{self.SERVICE_NAME}] Session expired or not found. Logging in...")
            self.login()
        else:
            print(f"[{self.SERVICE_NAME}] Existing session is valid.")

    def screenshot(self, name: str = "debug"):
        """Save a debug screenshot."""
        path = PROJECT_ROOT / f"debug_{self.SERVICE_NAME}_{name}.png"
        if self.page:
            self.page.screenshot(path=str(path))
            print(f"  Screenshot saved: {path}")

    def close(self):
        """Clean up browser resources."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        self.context = None
        self.page = None
        self.playwright = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.screenshot("error")
        self.close()
        return False
