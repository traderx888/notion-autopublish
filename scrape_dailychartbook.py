#!/usr/bin/env python3
"""Dailychartbook local artifact builder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from browser.scrapers.dailychartbook import run


def _ensure_utf8_stdout() -> None:
    stream = getattr(sys, "stdout", None)
    if stream is None:
        return
    encoding = getattr(stream, "encoding", "") or ""
    if encoding.lower() == "utf-8":
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Dailychartbook artifacts from local packet folders.")
    parser.add_argument("--root", help="Dailychartbook root directory. Falls back to DAILYCHARTBOOK_DIR.")
    parser.add_argument("--output-dir", help="Destination for normalized artifacts.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window when no --date is specified.")
    parser.add_argument("--date", dest="date_value", help="Only process a single chartbook date in YYYY-MM-DD format.")
    parser.add_argument("--taxonomy-path", help="Override taxonomy config path.")
    return parser


def main(argv=None) -> int:
    _ensure_utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        manifest = run(
            root_dir=Path(args.root) if args.root else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            days=args.days,
            date_value=args.date_value,
            taxonomy_path=Path(args.taxonomy_path) if args.taxonomy_path else None,
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
