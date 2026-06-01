"""
Daily Login Ceremony — manual login + immediate scrape for Playwright-based scrapers.

Problem: Playwright persistent contexts lose IndexedDB/refresh tokens on close/reopen,
and headless mode triggers anti-bot detection. This causes scrapers to fail silently.

Solution: Run this script each morning. It opens a *headed* browser for each service,
lets you log in manually, then scrapes immediately in the same session (no restart).
Results are written to the same output paths as standalone scripts.

Usage:
    python daily_login_ceremony.py                              # all 6 services
    python daily_login_ceremony.py --services deepvue substack  # selective
    python daily_login_ceremony.py --services seekingalpha      # SA only
    python daily_login_ceremony.py --check-only                 # validate sessions, no scrape
    python daily_login_ceremony.py --check-only --services notebooklm luxalgo
"""

import argparse
import io
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

PROJECT_ROOT = Path(__file__).resolve().parent
SESSIONS_DIR = PROJECT_ROOT / "browser" / "sessions"
SCRAPED_DIR = PROJECT_ROOT / "scraped_data"

ALL_SERVICES = [
    "deepvue", "substack", "seekingalpha",
    "sentimentrader", "luxalgo", "notebooklm",
]

# Display names for Telegram summary
SERVICE_DISPLAY = {
    "deepvue": "DeepVue",
    "substack": "Substack",
    "seekingalpha": "Seeking Alpha",
    "sentimentrader": "SentimentTrader",
    "luxalgo": "LuxAlgo",
    "notebooklm": "NotebookLM",
}

# Substack authors to scrape after login
SUBSTACK_AUTHORS = [
    ("capitalwars", "https://substack.com/@capitalwars", 3),
    ("fomosoc", "https://substack.com/@fomosoc", 2),
    ("semianalysis", "https://semianalysis.com", 2),
    ("finallynitin", "https://substack.com/@finallynitin", 2),
    ("sysls", "https://substack.com/@sysls", 2),
]

# NotebookLM paths (mirrors notebooklm_login.py)
NOTEBOOKLM_URL = "https://notebooklm.google.com/"
NOTEBOOKLM_STORAGE_DIR = Path.home() / ".notebooklm"
NOTEBOOKLM_STORAGE_PATH = NOTEBOOKLM_STORAGE_DIR / "storage_state.json"
NOTEBOOKLM_BROWSER_PROFILE = NOTEBOOKLM_STORAGE_DIR / "browser_profile"


def _now_hkt() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _now_hkt_iso() -> str:
    return _now_hkt().isoformat(timespec="seconds")


def _write_stamp(service: str, scrape_ok: bool, outputs: List[str],
                 check_only: bool = False):
    """Write ceremony stamp so mid-day tasks know we scraped today."""
    stamp_dir = SESSIONS_DIR / service
    stamp_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "date": _now_hkt().strftime("%Y-%m-%d"),
        "login_at": _now_hkt_iso(),
        "scrape_ok": scrape_ok,
        "check_only": check_only,
        "outputs": outputs,
    }
    (stamp_dir / "ceremony_stamp.json").write_text(
        json.dumps(stamp, indent=2), encoding="utf-8"
    )


def _wait_for_manual_login(page, message: str):
    """Pause and wait for user to complete login in the browser."""
    print(f"\n{'=' * 60}")
    print(f"  MANUAL LOGIN REQUIRED")
    print(f"  {message}")
    print(f"{'=' * 60}")
    input("  Press ENTER when you are logged in >>> ")
    print()


# ── DeepVue ──────────────────────────────────────────────────────────

def _ceremony_deepvue(check_only: bool = False) -> Dict:
    """Open DeepVue headed, login if needed, scrape dashboards."""
    from browser.scrapers.deepvue import DeepVueScraper

    print("\n" + "=" * 60)
    print("  SERVICE: DeepVue")
    print("=" * 60)

    scraper = DeepVueScraper(headless=False)
    scraper.start()

    try:
        # Check if already logged in
        if not scraper.is_logged_in():
            print("  [DeepVue] Not logged in — opening login page...")
            scraper.page.goto("https://app.deepvue.com", wait_until="domcontentloaded")
            scraper.page.wait_for_timeout(2000)
            _wait_for_manual_login(
                scraper.page,
                "Please log in to DeepVue:\n"
                "  1. Enter your email\n"
                "  2. Check email for verification code\n"
                "  3. Enter the code\n"
                "  4. Wait until the dashboard loads",
            )
            # Verify login succeeded
            if not scraper.is_logged_in():
                print("  [DeepVue] Login verification FAILED")
                _write_stamp("deepvue", False, [])
                return {"ok": False, "error": "Login failed after manual attempt"}
        else:
            print("  [DeepVue] Already logged in!")

        if check_only:
            print("  [DeepVue] Session valid (check-only mode)")
            _write_stamp("deepvue", True, [], check_only=True)
            return {"ok": True, "check_only": True}

        # Scrape in the same session — no restart
        print("  [DeepVue] Capturing dashboards...")
        results = scraper.run(dashboards=["market_overview", "preopen"])

        outputs = []
        if results.get("market_overview"):
            outputs.append("scraped_data/deepvue/market_overview.json")
        if results.get("preopen"):
            outputs.append("scraped_data/deepvue/preopen.json")

        _write_stamp("deepvue", bool(outputs), outputs)
        print(f"  [DeepVue] Done — captured {len(outputs)} dashboards")
        return {"ok": True, "dashboards": len(outputs), "outputs": outputs}

    except Exception as exc:
        print(f"  [DeepVue] ERROR: {exc}")
        _write_stamp("deepvue", False, [])
        return {"ok": False, "error": str(exc)}
    finally:
        scraper.close()


# ── Substack ─────────────────────────────────────────────────────────

def _ceremony_substack(check_only: bool = False) -> Dict:
    """Open Substack headed, login if needed, scrape all authors."""
    from scrape_substack_author import SubstackAuthorReader
    from browser.base import SCRAPED_DIR as BASE_SCRAPED_DIR

    print("\n" + "=" * 60)
    print("  SERVICE: Substack")
    print("=" * 60)

    reader = SubstackAuthorReader(headless=False)
    reader.start()

    try:
        # Navigate to substack and check login state
        reader.page.goto("https://substack.com/inbox", wait_until="domcontentloaded")
        reader.page.wait_for_timeout(3000)

        url = reader.page.url.lower()
        if "sign-in" in url or "login" in url or "account/login" in url:
            print("  [Substack] Not logged in — opening login page...")
            _wait_for_manual_login(
                reader.page,
                "Please log in to Substack:\n"
                "  1. Enter your email/password or use Google sign-in\n"
                "  2. Complete any 2FA if prompted\n"
                "  3. Wait until your inbox/feed loads",
            )
            # Verify
            reader.page.goto("https://substack.com/inbox", wait_until="domcontentloaded")
            reader.page.wait_for_timeout(3000)
            if "sign-in" in reader.page.url.lower():
                print("  [Substack] Login verification FAILED")
                _write_stamp("substack", False, [])
                return {"ok": False, "error": "Login failed", "authors": {}}
        else:
            print("  [Substack] Already logged in!")

        if check_only:
            print("  [Substack] Session valid (check-only mode)")
            _write_stamp("substack", True, [], check_only=True)
            return {"ok": True, "check_only": True}

        # Scrape all authors in the same session
        out_dir = BASE_SCRAPED_DIR / "substack_authors"
        out_dir.mkdir(parents=True, exist_ok=True)
        author_results = {}
        outputs = []

        for slug, url, limit in SUBSTACK_AUTHORS:
            print(f"\n  [Substack] Scraping {slug} ({url}, limit={limit})...")
            try:
                articles = reader.read_author_page(url, limit=limit)

                # Save individual articles
                for art in articles:
                    art_slug = art["title"].lower().replace(" ", "-")[:50]
                    art_slug = "".join(c for c in art_slug if c.isalnum() or c == "-")
                    filepath = out_dir / f"{art_slug}.json"
                    filepath.write_text(
                        json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8"
                    )

                # Save combined text
                combined = []
                for art in articles:
                    combined.append(f"{'=' * 60}")
                    combined.append(f"TITLE: {art['title']}")
                    combined.append(f"DATE: {art['date']}")
                    combined.append(f"URL: {art['url']}")
                    combined.append(f"{'=' * 60}")
                    combined.append(art["body_text"])
                    combined.append("\n")
                combined_path = out_dir / f"{slug}_latest.txt"
                combined_path.write_text("\n".join(combined), encoding="utf-8")

                author_results[slug] = {"ok": True, "articles": len(articles)}
                outputs.append(str(combined_path.relative_to(PROJECT_ROOT)))
                print(f"  [Substack] {slug}: {len(articles)} articles saved")

            except Exception as exc:
                print(f"  [Substack] {slug}: ERROR — {exc}")
                author_results[slug] = {"ok": False, "error": str(exc)}

        success_count = sum(1 for r in author_results.values() if r.get("ok"))
        _write_stamp("substack", success_count > 0, outputs)
        print(f"\n  [Substack] Done — {success_count}/{len(SUBSTACK_AUTHORS)} authors scraped")
        return {"ok": success_count > 0, "authors": author_results, "outputs": outputs}

    except Exception as exc:
        print(f"  [Substack] ERROR: {exc}")
        _write_stamp("substack", False, [])
        return {"ok": False, "error": str(exc), "authors": {}}
    finally:
        reader.close()


# ── Seeking Alpha ────────────────────────────────────────────────────

def _ceremony_seekingalpha(check_only: bool = False) -> Dict:
    """Open Seeking Alpha headed, login if needed, scrape P-model groups."""
    from scrape_sa_group import SAGroupReader, SA_GROUPS, write_bundle_outputs, _scrape_group

    print("\n" + "=" * 60)
    print("  SERVICE: Seeking Alpha (P-model)")
    print("=" * 60)

    reader = SAGroupReader(headless=False)
    reader.start()

    try:
        # Navigate to a group page to check login
        test_url = "https://rc.seekingalpha.com/group/pam-trade-summaries-read-only"
        reader.page.goto(test_url, wait_until="domcontentloaded")
        reader.page.wait_for_timeout(5000)

        url = reader.page.url.lower()
        if "login" in url or "sign_in" in url or "sign-in" in url:
            print("  [SA] Not logged in — opening login page...")
            reader.page.goto("https://seekingalpha.com/login", wait_until="domcontentloaded")
            reader.page.wait_for_timeout(2000)
            _wait_for_manual_login(
                reader.page,
                "Please log in to Seeking Alpha:\n"
                "  1. Enter your email/password\n"
                "  2. Complete any CAPTCHA if prompted\n"
                "  3. Wait until you see the SA homepage",
            )
            # Verify by trying to access the group again
            reader.page.goto(test_url, wait_until="domcontentloaded")
            reader.page.wait_for_timeout(5000)
            if "login" in reader.page.url.lower():
                print("  [SA] Login verification FAILED")
                _write_stamp("seekingalpha", False, [])
                return {"ok": False, "error": "Login failed", "groups": {}}
        else:
            print("  [SA] Already logged in!")

        if check_only:
            print("  [SA] Session valid (check-only mode)")
            _write_stamp("seekingalpha", True, [], check_only=True)
            return {"ok": True, "check_only": True}

        # Scrape all P-model groups in the same session
        group_keys = list(SA_GROUPS.keys())
        results = {}

        for group_key in group_keys:
            print(f"\n  [SA] Scraping {group_key}...")
            result = _scrape_group(reader, group_key)
            results[group_key] = result
            status = "OK" if result.get("success") else "FAILED"
            print(f"  [SA] {group_key}: {status} ({result.get('block_count', 0)} blocks)")

        # Write bundle outputs (merged positioning corpus + manifest)
        manifest = write_bundle_outputs(results)

        success_count = sum(1 for r in results.values() if r.get("success"))
        outputs = [
            str(Path(g.get("output_path", "")).relative_to(PROJECT_ROOT))
            for g in manifest.get("groups", {}).values()
            if g.get("success")
        ]
        _write_stamp("seekingalpha", success_count > 0, outputs)
        print(f"\n  [SA] Done — {success_count}/{len(group_keys)} groups scraped")
        return {"ok": success_count > 0, "groups": results, "outputs": outputs}

    except Exception as exc:
        print(f"  [SA] ERROR: {exc}")
        _write_stamp("seekingalpha", False, [])
        return {"ok": False, "error": str(exc), "groups": {}}
    finally:
        reader.close()


# ── SentimentTrader ──────────────────────────────────────────────────

def _ceremony_sentimentrader(check_only: bool = False) -> Dict:
    """Open SentimentTrader headed, login if needed, scrape dashboard."""
    from browser.scrapers.sentimentrader import SentimentTraderScraper

    print("\n" + "=" * 60)
    print("  SERVICE: SentimentTrader")
    print("=" * 60)

    scraper = SentimentTraderScraper(headless=False)
    scraper.start()

    try:
        if not scraper.is_logged_in():
            print("  [SentimentTrader] Not logged in — opening login page...")
            scraper.login()  # calls wait_for_user() internally
            if not scraper.is_logged_in():
                print("  [SentimentTrader] Login verification FAILED")
                _write_stamp("sentimentrader", False, [])
                return {"ok": False, "error": "Login failed after manual attempt"}
        else:
            print("  [SentimentTrader] Already logged in!")

        if check_only:
            print("  [SentimentTrader] Session valid (check-only mode)")
            _write_stamp("sentimentrader", True, [], check_only=True)
            return {"ok": True, "check_only": True}

        # Quick scrape — dashboard indicators only
        print("  [SentimentTrader] Scraping dashboard (quick mode)...")
        result = scraper.run(quick=True)

        output_path = result.get("output_path", "")
        outputs = [str(Path(output_path).relative_to(PROJECT_ROOT))] if output_path else []
        _write_stamp("sentimentrader", True, outputs)
        print(f"  [SentimentTrader] Done — dashboard captured")
        return {"ok": True, "outputs": outputs}

    except Exception as exc:
        print(f"  [SentimentTrader] ERROR: {exc}")
        _write_stamp("sentimentrader", False, [])
        return {"ok": False, "error": str(exc)}
    finally:
        scraper.close()


# ── LuxAlgo ──────────────────────────────────────────────────────────

def _ceremony_luxalgo(check_only: bool = False) -> Dict:
    """Open LuxAlgo headed, login if needed, scrape alerts."""
    from browser.scrapers.luxalgo import LuxAlgoScraper

    print("\n" + "=" * 60)
    print("  SERVICE: LuxAlgo")
    print("=" * 60)

    scraper = LuxAlgoScraper(headless=False)
    scraper.start()

    try:
        # is_logged_in() navigates to luxalgo.com which can be slow/timeout.
        # Catch timeout so the user can still interact with the browser.
        logged_in = False
        try:
            logged_in = scraper.is_logged_in()
        except Exception as nav_exc:
            print(f"  [LuxAlgo] Site navigation slow/timed out: {nav_exc}")
            print("  [LuxAlgo] Browser is open — you can navigate manually.")

        if not logged_in:
            print("  [LuxAlgo] Not logged in — attempting login...")
            try:
                scraper.login()  # auto-fills from env vars, or wait_for_user()
            except Exception:
                # login() also navigates; if it times out, fall back to manual
                _wait_for_manual_login(
                    scraper.page,
                    "Please log in to LuxAlgo manually in the browser:\n"
                    "  1. Go to https://www.luxalgo.com/features/quant/\n"
                    "  2. Log in with your credentials\n"
                    "  3. Wait until the quant dashboard loads",
                )
            # Re-check after login attempt
            try:
                logged_in = scraper.is_logged_in()
            except Exception:
                pass
            if not logged_in:
                print("  [LuxAlgo] Login verification FAILED")
                _write_stamp("luxalgo", False, [])
                return {"ok": False, "error": "Login failed after attempt"}
        else:
            print("  [LuxAlgo] Already logged in!")

        if check_only:
            print("  [LuxAlgo] Session valid (check-only mode)")
            _write_stamp("luxalgo", True, [], check_only=True)
            return {"ok": True, "check_only": True}

        # Scrape alerts
        print("  [LuxAlgo] Scraping alerts...")
        scraper.run()

        date_str = _now_hkt().strftime("%Y-%m-%d")
        output_path = f"scraped_data/luxalgo/{date_str}_alerts.json"
        outputs = [output_path]
        _write_stamp("luxalgo", True, outputs)
        print(f"  [LuxAlgo] Done — alerts saved")
        return {"ok": True, "outputs": outputs}

    except Exception as exc:
        print(f"  [LuxAlgo] ERROR: {exc}")
        _write_stamp("luxalgo", False, [])
        return {"ok": False, "error": str(exc)}
    finally:
        scraper.close()


# ── NotebookLM ───────────────────────────────────────────────────────

def _ceremony_notebooklm(check_only: bool = False) -> Dict:
    """Open NotebookLM headed, validate Google auth, refresh storage_state."""
    from playwright.sync_api import sync_playwright

    print("\n" + "=" * 60)
    print("  SERVICE: NotebookLM (Google OAuth)")
    print("=" * 60)

    NOTEBOOKLM_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    NOTEBOOKLM_BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

    pw = sync_playwright().start()
    try:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(NOTEBOOKLM_BROWSER_PROFILE),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--password-store=basic",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        if "notebooklm.google.com" not in page.url:
            print("  [NotebookLM] Not logged in — Google auth required...")
            _wait_for_manual_login(
                page,
                "Please log in to your Google account:\n"
                "  1. Complete Google sign-in in the browser\n"
                "  2. Wait until the NotebookLM homepage loads\n"
                "  3. You should see your notebooks list",
            )
            page.wait_for_timeout(3000)
            if "notebooklm.google.com" not in page.url:
                print("  [NotebookLM] Login verification FAILED")
                _write_stamp("notebooklm", False, [])
                context.close()
                return {"ok": False, "error": "Google login failed"}
        else:
            print("  [NotebookLM] Already logged in!")

        # Always refresh the storage_state (tokens may have been refreshed)
        context.storage_state(path=str(NOTEBOOKLM_STORAGE_PATH))
        context.close()

        outputs = [str(NOTEBOOKLM_STORAGE_PATH)]
        _write_stamp("notebooklm", True, outputs, check_only=check_only)
        mode_label = "check-only" if check_only else "auth refreshed"
        print(f"  [NotebookLM] Done — storage_state saved ({mode_label})")
        return {"ok": True, "check_only": check_only, "outputs": outputs}

    except Exception as exc:
        print(f"  [NotebookLM] ERROR: {exc}")
        _write_stamp("notebooklm", False, [])
        return {"ok": False, "error": str(exc)}
    finally:
        pw.stop()


# ── Telegram Summary ─────────────────────────────────────────────────

def _format_service_detail(service: str, result: Dict) -> str:
    """Format service-specific detail for Telegram summary."""
    if service == "deepvue":
        return f"{result.get('dashboards', 0)} dashboards"
    elif service == "substack":
        authors = result.get("authors", {})
        ok_count = sum(1 for a in authors.values() if a.get("ok"))
        return f"{ok_count}/{len(authors)} authors"
    elif service == "seekingalpha":
        groups = result.get("groups", {})
        ok_count = sum(1 for g in groups.values() if g.get("success"))
        return f"{ok_count}/{len(groups)} groups"
    elif service == "sentimentrader":
        return "dashboard captured"
    elif service == "luxalgo":
        return "alerts scraped"
    elif service == "notebooklm":
        return "auth refreshed"
    return "OK"


def _send_telegram_summary(results: Dict[str, Dict]):
    """Send a short ceremony summary to Telegram."""
    try:
        from tools.telegram_hub import send_to_destinations
    except ImportError:
        print("  [Telegram] telegram_hub not available, skipping notification")
        return

    parts = [f"<b>Morning Ceremony</b>  {_now_hkt().strftime('%Y-%m-%d %H:%M')} HKT\n"]

    for svc, r in results.items():
        name = SERVICE_DISPLAY.get(svc, svc)
        if r.get("check_only"):
            parts.append(f"{name}: session valid")
        elif r.get("ok"):
            detail = _format_service_detail(svc, r)
            parts.append(f"{name}: {detail}")
        else:
            parts.append(f"{name}: FAILED")

    message = "\n".join(parts)
    try:
        send_to_destinations(
            alert_key="morning_ceremony",
            messages=[message],
            parse_mode="HTML",
        )
        print(f"\n  [Telegram] Summary sent")
    except Exception as exc:
        print(f"\n  [Telegram] Send failed: {exc}")
        print(f"  Message was:\n{message}")


# ── Main ─────────────────────────────────────────────────────────────

CEREMONY_HANDLERS = {
    "deepvue": _ceremony_deepvue,
    "substack": _ceremony_substack,
    "seekingalpha": _ceremony_seekingalpha,
    "sentimentrader": _ceremony_sentimentrader,
    "luxalgo": _ceremony_luxalgo,
    "notebooklm": _ceremony_notebooklm,
}


def main():
    parser = argparse.ArgumentParser(
        description="Daily login ceremony — manual login + immediate scrape"
    )
    parser.add_argument(
        "--services",
        nargs="+",
        choices=ALL_SERVICES,
        default=ALL_SERVICES,
        help="Services to log in and scrape (default: all)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate sessions without scraping (fast pre-flight check)",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Skip Telegram summary notification",
    )
    args = parser.parse_args()

    mode = "CHECK-ONLY" if args.check_only else "LOGIN + SCRAPE"
    print(f"\n  Daily Login Ceremony — {_now_hkt().strftime('%Y-%m-%d %H:%M')} HKT")
    print(f"  Mode: {mode}")
    print(f"  Services: {', '.join(args.services)}")
    print()

    results = {}
    for service in args.services:
        handler = CEREMONY_HANDLERS[service]
        results[service] = handler(check_only=args.check_only)

    # Print summary
    print("\n" + "=" * 60)
    print("  CEREMONY SUMMARY")
    print("=" * 60)
    all_ok = True
    for service, result in results.items():
        if result.get("check_only"):
            status = "SESSION OK"
        elif result.get("ok"):
            status = "OK"
        else:
            status = "FAILED"
            all_ok = False
        print(f"  {service:20s} {status}")
    print("=" * 60)

    if not args.no_telegram:
        _send_telegram_summary(results)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
