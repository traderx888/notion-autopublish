"""Tests for notebooklm_research.youtube_discovery — YouTube search and filtering."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notebooklm_research.youtube_discovery import (
    build_search_queries,
    filter_recent_videos,
    search_ticker_videos,
)


# ── build_search_queries ──────────────────────────────────────


def test_build_queries_default():
    queries = build_search_queries("NVDA")
    assert any("earnings call" in q for q in queries)
    assert any("investor presentation" in q for q in queries)
    assert all("NVDA" in q for q in queries)


def test_build_queries_semianalysis_context():
    queries = build_search_queries("TSM", context={"source": "semianalysis"})
    assert any("supply chain" in q for q in queries)
    assert any("capex" in q for q in queries)


def test_build_queries_ep_context():
    queries = build_search_queries("XENE", context={"source": "stockbee_ep"})
    assert any("catalyst" in q for q in queries)


def test_build_queries_deepvue_context():
    queries = build_search_queries("XLK", context={"source": "deepvue_capscreen"})
    assert any("sector rotation" in q for q in queries)


# ── filter_recent_videos ──────────────────────────────────────


def test_filter_recent_videos_keeps_recent():
    videos = [
        {"url": "a", "upload_date": "20260301"},
        {"url": "b", "upload_date": "20250101"},  # old
        {"url": "c", "upload_date": ""},  # unknown date, keep
    ]
    filtered = filter_recent_videos(videos, max_age_days=90)
    urls = [v["url"] for v in filtered]
    assert "a" in urls
    assert "b" not in urls
    assert "c" in urls  # unknown date kept


def test_filter_recent_videos_all_old():
    videos = [
        {"url": "a", "upload_date": "20200101"},
        {"url": "b", "upload_date": "20200201"},
    ]
    assert filter_recent_videos(videos, max_age_days=30) == []


# ── search_ticker_videos (mocked) ────────────────────────────


def _make_ytdlp_output(video_id: str, title: str, upload_date: str = "20260315") -> str:
    return json.dumps({
        "id": video_id,
        "title": title,
        "channel": "TestChannel",
        "duration": 600,
        "upload_date": upload_date,
        "view_count": 1000,
        "description": "Test video",
    })


@patch("notebooklm_research.youtube_discovery._run_ytdlp")
def test_search_ticker_videos_deduplicates(mock_ytdlp):
    # Same video ID returned for different queries
    output = _make_ytdlp_output("abc123", "NVDA Earnings Q4")
    mock_ytdlp.return_value = MagicMock(returncode=0, stdout=output)

    videos = search_ticker_videos(
        "NVDA",
        queries=["NVDA earnings", "NVDA investor"],
        limit_per_query=1,
    )

    assert len(videos) == 1
    assert videos[0]["id"] == "abc123"
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=abc123"


@patch("notebooklm_research.youtube_discovery._run_ytdlp")
def test_search_ticker_videos_multiple_results(mock_ytdlp):
    output = "\n".join([
        _make_ytdlp_output("vid1", "Earnings Call"),
        _make_ytdlp_output("vid2", "Analyst Day"),
    ])
    mock_ytdlp.return_value = MagicMock(returncode=0, stdout=output)

    videos = search_ticker_videos("NVDA", queries=["NVDA earnings"], limit_per_query=2)

    assert len(videos) == 2
    assert {v["id"] for v in videos} == {"vid1", "vid2"}


@patch("notebooklm_research.youtube_discovery._run_ytdlp")
def test_search_ticker_videos_handles_error(mock_ytdlp):
    mock_ytdlp.return_value = MagicMock(returncode=1, stdout="", stderr="error")

    videos = search_ticker_videos("XENE", queries=["XENE earnings"])
    assert videos == []
