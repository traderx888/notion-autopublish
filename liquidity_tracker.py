from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from liquidity.composite import build_composite_liquidity_snapshot
from liquidity.config import load_liquidity_config
from liquidity.h_model_parser import parse_h_model_article
from liquidity.h_model_source import capture_latest_h_model, load_latest_h_model_article
from liquidity.internal_checker import build_internal_checker_snapshot
from liquidity.io import append_history_row, load_recent_history, write_json

PROJECT_ROOT = Path(__file__).resolve().parent


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_output_dir() -> Path:
    output_dir = Path(os.getenv("LIQUIDITY_OUTPUT_DIR", "outputs/liquidity")).expanduser()
    if not output_dir.is_absolute():
        output_dir = (PROJECT_ROOT / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _resolve_raw_dir() -> Path:
    raw_dir = Path(os.getenv("LIQUIDITY_RAW_DIR", "scraped_data/liquidity")).expanduser()
    if not raw_dir.is_absolute():
        raw_dir = (PROJECT_ROOT / raw_dir).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _missing_checker_snapshot(note: str) -> dict:
    return {
        "snapshot_at": _now_iso(),
        "excel_source": "",
        "screenshot_source": "",
        "ocr_available": False,
        "series": {"level": 0.0, "mom_5d": 0.0, "mom_20d": 0.0},
        "alert_hits": [],
        "signal_points": 0,
        "liquidity_direction": "UNKNOWN",
        "urgent_change": False,
        "available": False,
        "note": note,
    }


def run_liquidity_tracker(
    skip_h_capture: bool = False,
    skip_internal_checker: bool = False,
) -> dict:
    load_dotenv(override=False)
    now_iso = _now_iso()
    output_dir = _resolve_output_dir()
    raw_dir = _resolve_raw_dir()

    previous_h_model = _read_json(output_dir / "h_model_latest.json")
    if skip_h_capture:
        raw_capture = load_latest_h_model_article(raw_dir)
        h_status = "ok" if raw_capture else "missing"
    else:
        raw_capture = capture_latest_h_model(
            os.getenv("H_MODEL_AUTHOR_URL", "https://substack.com/@capitalwars"),
            limit=3,
            headless=os.getenv("H_MODEL_HEADLESS", "1").strip().lower() in {"1", "true", "yes", "on"},
        )
        h_status = raw_capture.get("capture_status", "missing") if raw_capture else "missing"

    if raw_capture is None:
        raw_capture = {"captured_at": now_iso, "articles": [], "screenshot_path": ""}
    if previous_h_model:
        raw_capture = {**raw_capture, "previous": previous_h_model}

    h_model_snapshot = parse_h_model_article(raw_capture, now_iso=now_iso)
    if h_model_snapshot.get("carry_forward"):
        h_status = "carry_forward"
    write_json(output_dir / "h_model_latest.json", h_model_snapshot)

    checker_status = "missing"
    if skip_internal_checker:
        checker_snapshot = _missing_checker_snapshot("Internal checker skipped by operator.")
    else:
        try:
            config = load_liquidity_config()
            checker_snapshot = build_internal_checker_snapshot(config["checker"], now_iso=now_iso)
            if checker_snapshot["available"] and checker_snapshot["ocr_available"]:
                checker_status = "ok"
            elif checker_snapshot["available"]:
                checker_status = "partial"
            else:
                checker_status = "missing"
        except FileNotFoundError as exc:
            checker_snapshot = _missing_checker_snapshot(str(exc))
        except Exception as exc:
            checker_snapshot = _missing_checker_snapshot(f"Internal checker invalid: {exc}")
            checker_status = "invalid"
    write_json(output_dir / "internal_checker_latest.json", checker_snapshot)

    history_path = output_dir / "liquidity_tracker_history.csv"
    prior_history = load_recent_history(history_path, limit=2)
    composite_snapshot = build_composite_liquidity_snapshot(
        h_model_snapshot,
        checker_snapshot,
        prior_history=prior_history,
        now_iso=now_iso,
    )
    composite_snapshot["status"] = {
        "h_model_capture": h_status,
        "internal_checker": checker_status,
    }
    write_json(output_dir / "liquidity_tracker_latest.json", composite_snapshot)

    append_history_row(
        history_path,
        {
            "generated_at": composite_snapshot["generated_at"],
            "regime": composite_snapshot["composite"]["regime"],
            "trading_bias": composite_snapshot["composite"]["trading_bias"],
            "h_direction": h_model_snapshot.get("liquidity_direction", "UNKNOWN"),
            "checker_direction": checker_snapshot.get("liquidity_direction", "UNKNOWN"),
            "override_active": str(composite_snapshot["composite"]["override_active"]),
            "override_reason": composite_snapshot["composite"]["override_reason"],
            "confidence": composite_snapshot["composite"]["confidence"],
        },
    )
    print(
        "Liquidity Tracker: "
        f"{composite_snapshot['composite']['regime']} | "
        f"{composite_snapshot['composite']['confidence']} | "
        f"override={composite_snapshot['composite']['override_active']}"
    )
    return composite_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Composite liquidity tracker runner")
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Run the liquidity tracker")
    run_parser.add_argument("--skip-h-capture", action="store_true")
    run_parser.add_argument("--skip-internal-checker", action="store_true")
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return 1

    run_liquidity_tracker(
        skip_h_capture=args.skip_h_capture,
        skip_internal_checker=args.skip_internal_checker,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
