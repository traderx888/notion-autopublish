"""YouTube video discovery for ticker research via yt-dlp.

Searches YouTube for earnings calls, analyst coverage, and investor
presentations per ticker. Adapted from youtube-search skill's yt_search.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# Ensure deno is on PATH (required by yt-dlp 2026+ for YouTube)
_DENO_DIR = Path(os.path.expanduser("~")) / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
for _d in _DENO_DIR.glob("DenoLand.Deno*"):
    if _d.is_dir():
        os.environ["PATH"] = str(_d) + os.pathsep + os.environ.get("PATH", "")
        break

_COOKIES_FILE = (
    Path(__file__).resolve().parents[1]
    / ".."
    / ".claude"
    / "skills"
    / "youtube-search"
    / "data"
    / "youtube_cookies.txt"
)


def _run_ytdlp(
    args: list[str],
    *,
    timeout: int = 30,
    cookies_file: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run yt-dlp with given args and return result."""
    cmd = ["yt-dlp", "--no-warnings", "--encoding", "utf-8"]
    cfile = cookies_file or _COOKIES_FILE
    if cfile.exists():
        cmd.extend(["--cookies", str(cfile)])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def build_search_queries(ticker: str, context: dict | None = None) -> list[str]:
    """Build context-aware YouTube search queries for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA").
        context: Signal target dict with ``source`` key.

    Returns:
        List of search query strings.
    """
    ctx = context or {}
    source = ctx.get("source", "")
    year = datetime.now().year

    base_queries = [
        f"{ticker} earnings call {year}",
        f"{ticker} investor presentation {year}",
    ]

    if source in ("semianalysis", "fomo"):
        base_queries.extend([
            f"{ticker} supply chain analysis {year}",
            f"{ticker} capex roadmap {year}",
        ])
    elif source == "stockbee_ep":
        base_queries.extend([
            f"{ticker} stock analysis {year}",
            f"{ticker} catalyst {year}",
        ])
    elif source in ("deepvue_capscreen", "deepvue_stage"):
        base_queries.extend([
            f"{ticker} sector rotation {year}",
            f"{ticker} technical analysis {year}",
        ])

    return base_queries


def search_ticker_videos(
    ticker: str,
    queries: list[str] | None = None,
    *,
    limit_per_query: int = 2,
    cookies_file: Path | None = None,
) -> list[dict[str, Any]]:
    """Search YouTube for videos related to a ticker.

    Args:
        ticker: Stock ticker symbol.
        queries: Custom search queries. If None, uses defaults.
        limit_per_query: Max results per query.
        cookies_file: Optional path to youtube cookies.

    Returns:
        Deduplicated list of video metadata dicts.
    """
    if queries is None:
        queries = build_search_queries(ticker)

    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []

    for query in queries:
        args = [
            f"ytsearch{limit_per_query}:{query}",
            "--flat-playlist",
            "--dump-json",
            "--no-download",
        ]
        try:
            proc = _run_ytdlp(args, timeout=30, cookies_file=cookies_file)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

        if proc.returncode != 0:
            continue

        for line in proc.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            video_id = data.get("id", "")
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            results.append({
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "id": video_id,
                "title": data.get("title", ""),
                "channel": data.get("channel") or data.get("uploader", ""),
                "duration": data.get("duration"),
                "upload_date": data.get("upload_date", ""),
                "view_count": data.get("view_count"),
                "description": (data.get("description") or "")[:200],
            })

    return results


def filter_recent_videos(
    videos: list[dict[str, Any]],
    *,
    max_age_days: int = 90,
) -> list[dict[str, Any]]:
    """Filter videos to keep only recent uploads.

    Args:
        videos: List of video dicts with ``upload_date`` in YYYYMMDD format.
        max_age_days: Maximum age in days.

    Returns:
        Filtered list.
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)
    cutoff_str = cutoff.strftime("%Y%m%d")

    filtered = []
    for v in videos:
        upload = v.get("upload_date", "")
        # Keep videos with unknown date (better to include than miss)
        if not upload or upload >= cutoff_str:
            filtered.append(v)

    return filtered
