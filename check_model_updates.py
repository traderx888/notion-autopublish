"""
Periodic update checker for H-Model (Capital Wars) and P-Model (PAM/SA).

Runs every 2 hours via Windows Task Scheduler (05:00-23:00 HKT).
Compares fresh scrape results against saved state.
Sends a Telegram alert only when new content is detected.
"""

from __future__ import annotations

import argparse
import html as html_mod
import io
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

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
STATE_FILE = PROJECT_ROOT / "scraped_data" / ".model_check_state.json"
H_MODEL_RAW = PROJECT_ROOT / "scraped_data" / "liquidity" / "h_model_latest_raw.json"
P_MODEL_MANIFEST = PROJECT_ROOT / "scraped_data" / "sa_group_p_model_manifest.json"

HKT = ZoneInfo("Asia/Hong_Kong")
SCHEDULE_START_HOUR = 5
SCHEDULE_END_HOUR = 23


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_within_schedule() -> bool:
    now_hkt = datetime.now(HKT)
    return SCHEDULE_START_HOUR <= now_hkt.hour < SCHEDULE_END_HOUR


def _read_h_model_raw() -> dict:
    if not H_MODEL_RAW.exists():
        return {}
    try:
        return json.loads(H_MODEL_RAW.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _extract_h_article_urls(payload: dict) -> list[str]:
    articles = payload.get("articles") or []
    return [a.get("url", "") for a in articles if a.get("url")]


def check_h_model(prev_state: dict) -> tuple[bool, dict, dict | None]:
    h_prev = prev_state.get("h_model", {})
    prev_urls = set(h_prev.get("article_urls", []))

    try:
        from liquidity.h_model_source import capture_latest_h_model

        author_url = os.getenv("H_MODEL_AUTHOR_URL", "https://substack.com/@capitalwars")
        payload = capture_latest_h_model(author_url, limit=3, headless=True)

        if not payload.get("available"):
            print("  H-Model scrape returned unavailable")
            return False, dict(h_prev), None

        new_urls = _extract_h_article_urls(payload)
        new_state = {
            "article_urls": new_urls,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        if not prev_urls:
            print("  H-Model: first run, saving baseline")
            return False, new_state, None

        added = set(new_urls) - prev_urls
        if not added:
            return False, new_state, None

        from liquidity.h_model_parser import parse_h_model_article

        parsed = parse_h_model_article(payload)
        return True, new_state, parsed

    except Exception as exc:
        print(f"  H-Model check failed: {exc}")
        traceback.print_exc()
        return False, dict(h_prev), None


def _read_p_model_manifest() -> dict:
    if not P_MODEL_MANIFEST.exists():
        return {}
    try:
        return json.loads(P_MODEL_MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _manifest_fingerprint(manifest: dict) -> dict[str, dict[str, int]]:
    groups = manifest.get("groups", {})
    return {
        key: {
            "block_count": int(g.get("block_count", 0)),
            "char_count": int(g.get("char_count", 0)),
        }
        for key, g in groups.items()
    }


def _extract_first_line(group_key: str) -> str:
    from scrape_sa_group import SA_GROUPS, PROJECT_ROOT as SA_ROOT

    spec = SA_GROUPS.get(group_key, {})
    output_rel = spec.get("output", "")
    if not output_rel:
        return ""
    path = SA_ROOT / output_rel
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("==="):
                return stripped[:120]
    except OSError:
        pass
    return ""


def check_p_model(prev_state: dict) -> tuple[bool, dict, dict | None]:
    p_prev = prev_state.get("p_model", {})
    prev_fingerprint = p_prev.get("groups", {})

    try:
        before_manifest = _read_p_model_manifest()
        before_fp = _manifest_fingerprint(before_manifest)

        if not prev_fingerprint and before_fp:
            prev_fingerprint = before_fp

        from scrape_sa_group import (
            SAGroupReader,
            _scrape_group,
            _write_single_output,
            resolve_group_keys,
            write_bundle_outputs,
        )

        group_keys = resolve_group_keys()
        results = {}
        with SAGroupReader(headless=True) as reader:
            for group_key in group_keys:
                print(f"    Scraping {group_key}...")
                result = _scrape_group(reader, group_key)
                results[group_key] = result
                _write_single_output(group_key, str(result.get("content", "") or ""))

        write_bundle_outputs(results)

        after_manifest = _read_p_model_manifest()
        after_fp = _manifest_fingerprint(after_manifest)

        new_state = {
            "groups": after_fp,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        if not prev_fingerprint:
            print("  P-Model: first run, saving baseline")
            return False, new_state, None

        delta = {}
        for key, after_vals in after_fp.items():
            before_vals = prev_fingerprint.get(key, {"block_count": 0, "char_count": 0})
            block_d = after_vals["block_count"] - before_vals["block_count"]
            char_d = after_vals["char_count"] - before_vals["char_count"]
            if block_d != 0 or char_d != 0:
                delta[key] = {
                    "block_delta": block_d,
                    "char_delta": char_d,
                    "first_line": _extract_first_line(key),
                }

        if not delta:
            return False, new_state, None

        return True, new_state, delta

    except Exception as exc:
        print(f"  P-Model check failed: {exc}")
        traceback.print_exc()
        return False, dict(p_prev), None


def build_telegram_message(
    h_updated: bool,
    h_parsed: dict | None,
    p_updated: bool,
    p_delta: dict | None,
) -> str:
    now_hkt = datetime.now(HKT).strftime("%Y-%m-%d %H:%M HKT")
    parts = [f"<b>Model Update Alert</b>", f"<i>{now_hkt}</i>", ""]

    if h_updated and h_parsed:
        title = html_mod.escape(h_parsed.get("title", "Unknown")[:80])
        direction = h_parsed.get("liquidity_direction", "UNKNOWN")
        bias = h_parsed.get("market_bias", "UNKNOWN")
        score = h_parsed.get("signal_score", 0)
        url = h_parsed.get("article_url", "")
        evidence = h_parsed.get("evidence", [])[:3]

        parts.append("<b>[H-Model] New Capital Wars Article</b>")
        parts.append(f"Title: {title}")
        parts.append(f"Direction: <b>{direction}</b> | Bias: <b>{bias}</b> | Score: {score}")
        if url:
            parts.append(f'<a href="{url}">Read article</a>')
        if evidence:
            parts.append("")
            parts.append("<b>Key evidence:</b>")
            for ev in evidence:
                snippet = html_mod.escape(ev[:150])
                parts.append(f"  - {snippet}")
        parts.append("")

    if p_updated and p_delta:
        parts.append("<b>[P-Model] SA Groups Updated</b>")
        for group_key, delta in p_delta.items():
            block_d = delta.get("block_delta", 0)
            char_d = delta.get("char_delta", 0)
            first_line = html_mod.escape(delta.get("first_line", "")[:120])
            sign_b = "+" if block_d >= 0 else ""
            sign_c = "+" if char_d >= 0 else ""
            parts.append(
                f"  - <b>{html_mod.escape(group_key)}</b>: blocks {sign_b}{block_d}, chars {sign_c}{char_d}"
            )
            if first_line:
                parts.append(f"    <i>{first_line}</i>")
        parts.append("")

    return "\n".join(parts).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check H-Model and P-Model for updates, send Telegram alert if new content found."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print message instead of sending")
    parser.add_argument("--force", action="store_true", help="Ignore schedule window check")
    parser.add_argument("--h-only", action="store_true", help="Only check H-Model")
    parser.add_argument("--p-only", action="store_true", help="Only check P-Model")
    return parser.parse_args()


def main() -> int:
    load_dotenv(override=False)
    args = parse_args()

    if not args.force and not is_within_schedule():
        now_hkt = datetime.now(HKT).strftime("%H:%M HKT")
        print(f"Outside schedule window ({SCHEDULE_START_HOUR:02d}:00-{SCHEDULE_END_HOUR:02d}:00 HKT). Now: {now_hkt}. Exiting.")
        return 0

    state = load_state()
    h_updated, h_parsed = False, None
    p_updated, p_delta = False, None

    if not args.p_only:
        print("Checking H-Model (Capital Wars)...")
        h_updated, h_new_state, h_parsed = check_h_model(state)
        state["h_model"] = h_new_state
        print(f"  H-Model: {'NEW content detected' if h_updated else 'no change'}")

    if not args.h_only:
        print("Checking P-Model (SA groups)...")
        p_updated, p_new_state, p_delta = check_p_model(state)
        state["p_model"] = p_new_state
        print(f"  P-Model: {'NEW content detected' if p_updated else 'no change'}")

    save_state(state)

    if not h_updated and not p_updated:
        print("No updates. No Telegram sent.")
        return 0

    updates = []
    if h_updated:
        updates.append("H-Model")
    if p_updated:
        updates.append("P-Model")
    print(f"Updates found: {', '.join(updates)}")

    message = build_telegram_message(h_updated, h_parsed, p_updated, p_delta)
    if not message.strip():
        print("Empty message body. Skipping Telegram.")
        return 0

    if args.dry_run:
        print("=" * 56)
        print("DRY RUN — message that would be sent:")
        print("=" * 56)
        print(message)
        print("=" * 56)
        return 0

    try:
        from tools.telegram_hub import load_telegram_credentials, send_message, split_message

        token, chat_id = load_telegram_credentials()
        for chunk in split_message(message, max_length=3900):
            send_message(bot_token=token, chat_id=chat_id, text=chunk, parse_mode="HTML")
        print("Telegram alert sent successfully.")
    except Exception as exc:
        print(f"Telegram send failed: {exc}")
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
