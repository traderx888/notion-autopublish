from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.dashboard_freshness import (
    OUTPUT_DIR,
    SCRAPED_DATA_DIR,
    build_market_breadth_snapshot,
    now_hkt_iso,
    read_json,
    render_dashboard_html,
    write_json,
)


DEFAULT_OUTPUT = OUTPUT_DIR / "dashboard.html"
DEFAULT_MIRROR = SCRAPED_DATA_DIR / "dashboard.html"
SNAPSHOT_PATH = SCRAPED_DATA_DIR / "dashboard" / "market_breadth_latest.json"
REFRESH_STATUS_PATH = SCRAPED_DATA_DIR / "dashboard" / "refresh_status.json"
SMM_PATH = SCRAPED_DATA_DIR / "smm" / "latest.json"
DEEPVUE_PATH = SCRAPED_DATA_DIR / "deepvue" / "market_overview.json"
HK_PATH = SCRAPED_DATA_DIR / "hk_breadth" / "latest.json"


def _collect_candidate_timestamps(*payloads: dict[str, Any] | None) -> list[str]:
    candidates: list[str] = []
    for payload in payloads:
        if not payload:
            continue
        for key in ("generatedAt", "capturedAt", "lastAttemptAt"):
            value = payload.get(key)
            if value:
                candidates.append(value)
        for entry in (payload.get("sources") or {}).values():
            if isinstance(entry, dict):
                for key in ("capturedAt", "lastAttemptAt"):
                    value = entry.get(key)
                    if value:
                        candidates.append(value)
    return candidates


def _pick_generated_at(
    smm_payload: dict[str, Any] | None,
    deepvue_payload: dict[str, Any] | None,
    hk_payload: dict[str, Any] | None,
    refresh_status: dict[str, Any] | None,
    existing_snapshot: dict[str, Any] | None,
) -> str:
    candidates = _collect_candidate_timestamps(
        smm_payload,
        deepvue_payload,
        hk_payload,
        refresh_status,
        existing_snapshot,
    )
    return max(candidates) if candidates else now_hkt_iso()


def build_dashboard(
    *,
    dashboard_path: Path = DEFAULT_OUTPUT,
    mirror_path: Path = DEFAULT_MIRROR,
) -> dict[str, Any]:
    smm_payload = read_json(SMM_PATH)
    deepvue_payload = read_json(DEEPVUE_PATH)
    hk_payload = read_json(HK_PATH)
    refresh_status = read_json(REFRESH_STATUS_PATH)
    existing_snapshot = read_json(SNAPSHOT_PATH)
    generated_at = _pick_generated_at(
        smm_payload,
        deepvue_payload,
        hk_payload,
        refresh_status,
        existing_snapshot,
    )

    snapshot = build_market_breadth_snapshot(
        smm_payload,
        deepvue_payload,
        hk_payload,
        refresh_status=refresh_status,
        generated_at=generated_at,
    )
    write_json(SNAPSHOT_PATH, snapshot)

    template_html = dashboard_path.read_text(encoding="utf-8")
    rendered = render_dashboard_html(template_html, snapshot)
    dashboard_path.write_text(rendered, encoding="utf-8")
    mirror_path.write_text(rendered, encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the Market Breadth section in output/dashboard.html.")
    parser.add_argument(
        "--dashboard",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the dashboard HTML file to rebuild.",
    )
    parser.add_argument(
        "--mirror",
        type=Path,
        default=DEFAULT_MIRROR,
        help="Optional local mirror path for the rebuilt dashboard HTML.",
    )
    args = parser.parse_args()

    snapshot = build_dashboard(dashboard_path=args.dashboard, mirror_path=args.mirror)
    print("Dashboard rebuilt from source artifacts:")
    for source_key, source in snapshot["sources"].items():
        print(
            f"  - {source_key}: {source['status']} | marketDate={source.get('marketDate')} | "
            f"capturedAt={source.get('capturedAt')}"
        )
    print(f"Snapshot artifact: {SNAPSHOT_PATH}")
    print(f"Dashboard output: {args.dashboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
