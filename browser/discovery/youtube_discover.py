"""YouTube content discovery -- find relevant videos to comment on.

Uses yt-dlp ytsearch to find recent videos matching brand topics,
then scores them for relevance.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HKT = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class DiscoveryResult:
    url: str
    title: str
    author: str
    content_snippet: str
    engagement: dict
    relevance_score: float
    platform: str
    discovered_at: str


def _score_relevance(title: str, description: str, config: dict) -> float:
    """Score how relevant a video is to brand topics."""
    text = (title + " " + description).lower()
    keywords = (
        config["seo"]["target_keywords_en"] +
        config["seo"]["target_keywords_zh"] +
        [t.replace("_", " ") for t in config["topics"]["primary"]] +
        [t.replace("_", " ") for t in config["topics"]["secondary"]]
    )
    matches = sum(1 for kw in keywords if kw.lower() in text)
    return min(matches / 4.0, 1.0)


def discover(config: dict, limit: int = 10,
             query: str | None = None) -> list[DiscoveryResult]:
    """Find relevant YouTube videos using yt-dlp search.

    Args:
        config: Brand identity config dict
        limit: Max results to return
        query: Override search query (default: uses config discovery_queries)
    """
    yt_config = config["platforms"].get("youtube", {})
    queries = [query] if query else yt_config.get("discovery_queries", [])

    all_results = []
    seen_ids = set()

    for q in queries:
        videos = _search_youtube(q, max_results=5)
        for v in videos:
            vid_id = v.get("id", "")
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)

            title = v.get("title", "") or ""
            description = (v.get("description") or "")[:500]
            score = _score_relevance(title, description, config)

            if score < 0.2:
                continue

            all_results.append(DiscoveryResult(
                url=f"https://www.youtube.com/watch?v={vid_id}",
                title=title,
                author=v.get("channel", v.get("uploader", "Unknown")),
                content_snippet=description[:300],
                engagement={
                    "views": v.get("view_count", 0),
                    "likes": v.get("like_count", 0),
                    "comments": v.get("comment_count", 0),
                },
                relevance_score=round(score, 2),
                platform="youtube",
                discovered_at=datetime.now(HKT).isoformat(),
            ))

        if len(all_results) >= limit * 2:
            break

    # Sort by relevance, then by views
    all_results.sort(key=lambda r: (r.relevance_score, r.engagement.get("views", 0)),
                     reverse=True)
    return all_results[:limit]


def discover_by_channel(channel_names: list[str], config: dict,
                        limit: int = 5) -> list[DiscoveryResult]:
    """Find recent videos from specific target channels."""
    results = []

    for channel in channel_names:
        videos = _search_youtube(f"{channel} latest", max_results=3)
        for v in videos:
            title = v.get("title", "") or ""
            description = (v.get("description") or "")[:500]

            results.append(DiscoveryResult(
                url=f"https://www.youtube.com/watch?v={v.get('id', '')}",
                title=title,
                author=v.get("channel", v.get("uploader", channel)),
                content_snippet=description[:300],
                engagement={
                    "views": v.get("view_count", 0),
                    "likes": v.get("like_count", 0),
                },
                relevance_score=0.8,  # high relevance since we targeted them
                platform="youtube",
                discovered_at=datetime.now(HKT).isoformat(),
            ))

    return results[:limit]


def _search_youtube(query: str, max_results: int = 5) -> list[dict]:
    """Search YouTube via yt-dlp and return video metadata."""
    try:
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--no-download",
            "--flat-playlist",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"  yt-dlp search failed: {result.stderr[:200]}", file=sys.stderr)
            return []

        videos = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    videos.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return videos

    except FileNotFoundError:
        print("  yt-dlp not installed. Install with: pip install yt-dlp", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print("  yt-dlp search timed out", file=sys.stderr)
        return []
