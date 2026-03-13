from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from liquidity.h_model_source import capture_latest_h_model


def main() -> int:
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description="Capture latest Michael Howell H-model updates.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--limit", type=int, default=3, help="Number of posts to inspect")
    args = parser.parse_args()

    payload = capture_latest_h_model(
        os.getenv("H_MODEL_AUTHOR_URL", "https://substack.com/@capitalwars"),
        limit=args.limit,
        headless=args.headless,
    )
    print(f"H-model capture: {payload['capture_status']} | articles={len(payload.get('articles', []))}")
    return 0 if payload.get("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())

