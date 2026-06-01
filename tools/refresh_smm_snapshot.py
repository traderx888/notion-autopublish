from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import requests

from tools.dashboard_freshness import (
    SCRAPED_DATA_DIR,
    SMM_SOURCE_URL,
    now_hkt_iso,
    parse_smm_csv,
    write_json,
)


DEFAULT_OUTPUT = SCRAPED_DATA_DIR / "smm" / "latest.json"


def refresh_smm_snapshot(output_path: Path = DEFAULT_OUTPUT, timeout: int = 30) -> dict:
    response = requests.get(SMM_SOURCE_URL, timeout=timeout)
    response.raise_for_status()
    payload = parse_smm_csv(response.text, captured_at=now_hkt_iso())
    write_json(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the normalized SMM breadth snapshot.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the normalized SMM JSON artifact.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for the published Google Sheet.",
    )
    args = parser.parse_args()

    payload = refresh_smm_snapshot(output_path=args.output, timeout=args.timeout)
    metrics = payload["metrics"]
    print(
        "SMM snapshot refreshed:",
        payload["marketDate"],
        f"MA40={metrics.get('ma40Pct'):.2f}%",
        f"5d={metrics.get('ratio5d'):.2f}",
        f"10d={metrics.get('ratio10d'):.2f}",
    )
    print(f"Artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
