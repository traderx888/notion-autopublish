#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from ciovacco.feed import capture_ciovacco_feed, persist_ciovacco_artifact
from ciovacco.notebooklm_sync import resolve_notebooklm_sync_config, sync_ciovacco_notebooklm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture the latest CiovaccoCapital YouTube update.")
    parser.add_argument("--video-url", help="Override the channel feed and capture a specific video URL.")
    parser.add_argument("--output-dir", help="Directory for Ciovacco artifacts.")
    parser.add_argument("--channel-id", help="Override the default CiovaccoCapital channel ID.")
    parser.add_argument(
        "--sync-notebooklm",
        action="store_true",
        help="Enrich the captured artifact with NotebookLM using a configured notebook.",
    )
    parser.add_argument("--notebook-id", help="NotebookLM notebook ID. Falls back to CIOVACCO_NOTEBOOKLM_NOTEBOOK_ID.")
    parser.add_argument(
        "--notebooklm-storage",
        help="Path to NotebookLM storage_state.json. Falls back to NOTEBOOKLM_STORAGE_PATH.",
    )
    return parser


def run_notebooklm_sync(payload: dict, *, notebook_id: str, storage_path: str | None = None) -> dict:
    return asyncio.run(
        sync_ciovacco_notebooklm(
            payload,
            notebook_id=notebook_id,
            storage_path=storage_path,
        )
    )


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = capture_ciovacco_feed(
        output_dir=args.output_dir,
        channel_id=args.channel_id,
        video_url=args.video_url,
    )
    if args.sync_notebooklm:
        try:
            config = resolve_notebooklm_sync_config(
                notebook_id=args.notebook_id,
                storage_path=args.notebooklm_storage,
                env=dict(os.environ),
            )
        except ValueError as exc:
            parser.error(str(exc))
        try:
            payload["notebooklm"] = run_notebooklm_sync(
                payload,
                notebook_id=str(config["notebook_id"]),
                storage_path=config.get("storage_path"),
            )
        except Exception as exc:
            print(f"NotebookLM sync failed: {exc}", file=sys.stderr)
            return 1
        payload = persist_ciovacco_artifact(payload, output_dir=args.output_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
