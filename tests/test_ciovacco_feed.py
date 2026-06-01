from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_ciovacco
from ciovacco import feed


def test_parse_latest_feed_entry_selects_most_recent_video():
    xml_text = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <entry>
        <yt:videoId>older123</yt:videoId>
        <title>Older update</title>
        <published>2026-03-15T14:00:00+00:00</published>
        <updated>2026-03-15T14:05:00+00:00</updated>
        <link rel="alternate" href="https://www.youtube.com/watch?v=older123" />
      </entry>
      <entry>
        <yt:videoId>latest456</yt:videoId>
        <title>Latest update</title>
        <published>2026-03-21T14:00:00+00:00</published>
        <updated>2026-03-21T14:05:00+00:00</updated>
        <link rel="alternate" href="https://www.youtube.com/watch?v=latest456" />
      </entry>
    </feed>
    """

    entry = feed.parse_latest_feed_entry(xml_text)

    assert entry["video_id"] == "latest456"
    assert entry["title"] == "Latest update"
    assert entry["video_url"] == "https://www.youtube.com/watch?v=latest456"
    assert entry["published"] == "2026-03-21T14:00:00+00:00"


def test_pick_preferred_caption_track_prefers_english_manual_then_auto():
    info = {
        "subtitles": {
            "en": [
                {"ext": "vtt", "url": "https://example.com/manual.vtt"},
            ]
        },
        "automatic_captions": {
            "en-US": [
                {"ext": "vtt", "url": "https://example.com/auto.vtt"},
            ]
        },
    }

    track = feed.pick_preferred_caption_track(info)

    assert track == {
        "language": "en",
        "kind": "subtitles",
        "ext": "vtt",
        "url": "https://example.com/manual.vtt",
    }


def test_extract_ratio_mentions_normalizes_slash_and_versus_patterns():
    text = "Watch XLY/XLP, IEF versus LQD, and qqq vs spy. XLY/XLP remains the key ratio."

    mentions = feed.extract_ratio_mentions(text)

    assert mentions == [
        {"ratio": "XLY/XLP", "count": 2},
        {"ratio": "IEF/LQD", "count": 1},
        {"ratio": "QQQ/SPY", "count": 1},
    ]


def test_extract_ratio_mentions_supports_relative_to_phrasing():
    text = "XLK relative to SPY is intact. Have the long-term trends flipped in favor of XLF financials relative to XLK? Not yet."

    mentions = feed.extract_ratio_mentions(text)

    assert {"ratio": "XLK/SPY", "count": 1} in mentions
    assert {"ratio": "XLF/XLK", "count": 1} in mentions


def test_extract_keyword_hits_counts_technical_terms_case_insensitively():
    text = "AVWAP support held. Bollinger bands are rising. Another avwap test matters."

    hits = feed.extract_keyword_hits(text)

    assert hits["AVWAP"] == 2
    assert hits["Bollinger"] == 1


def test_normalize_transcript_text_removes_consecutive_duplicates():
    text = "Line one\nLine one\nLine two\n\nLine two\nLine three\n"

    normalized = feed.normalize_transcript_text(text)

    assert normalized == "Line one\nLine two\nLine three"


def test_build_ciovacco_analysis_extracts_ratio_reason_and_action():
    transcript = "\n".join(
        [
            "The main topic in this environment is the Strait of Hormuz.",
            "The market tends to remain weak and volatile until the news becomes less bad.",
            "The base case is we are treating this as a correction within the context of a secular bull market.",
            "XLK relative to SPY is over? The answer is no.",
            "The last thing it did was make a higher high.",
            "It has not made a substantial or important lower low.",
            "RSP relative to XLK still batting 0 for 5 monthly cloud.",
            "If we get a monthly close below the blue span, the odds of additional downside would increase.",
            "Have the long-term trends flipped in favor of XLF financials relative to XLK? Not yet.",
            "Dropping below the cloud here, especially if you get a monthly close below it, could potentially be significant.",
            "Tech FTEC relative to SPY tells us to keep an open mind about better than expected outcomes.",
            "This chart isn't screaming a major concern about a deflationary or traditional economic recession.",
        ]
    )

    analysis = feed.build_ciovacco_analysis(transcript)

    assert analysis["core_conclusion"].startswith("Base case")
    assert "Strait of Hormuz" in analysis["situation"]
    xlk_spy = next(item for item in analysis["ratio_signals"] if item["ratio"] == "XLK/SPY")
    assert "not over" in xlk_spy["signal"].lower()
    assert "higher high" in xlk_spy["reason"].lower()
    assert "rotation" in xlk_spy["action"].lower()
    rsp_xlk = next(item for item in analysis["ratio_signals"] if item["ratio"] == "RSP/XLK")
    assert "monthly close" in rsp_xlk["action"].lower()
    xlf_xlk = next(item for item in analysis["ratio_signals"] if item["ratio"] == "XLF/XLK")
    assert "not yet" in xlf_xlk["signal"].lower()
    assert "significant" in xlf_xlk["reason"].lower()


def test_capture_ciovacco_feed_writes_latest_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        feed,
        "_discover_latest_video",
        lambda channel_id, session=None: {
            "video_id": "6JCqUhMsPeM",
            "title": "WAR: How To Handle A Correction That Morphs Into A 20-50% Drawdown",
            "video_url": "https://www.youtube.com/watch?v=6JCqUhMsPeM",
            "published": "2026-03-21T08:02:14+00:00",
            "updated": "2026-03-21T08:02:14+00:00",
        },
    )
    monkeypatch.setattr(
        feed,
        "_extract_video_info",
        lambda video_url: {
            "id": "6JCqUhMsPeM",
            "title": "WAR: How To Handle A Correction That Morphs Into A 20-50% Drawdown",
            "upload_date": "20260321",
            "duration_string": "40:30",
            "channel": "CiovaccoCapital",
            "uploader_id": "@CiovaccoCapital",
            "subtitles": {},
            "automatic_captions": {
                "en": [{"ext": "vtt", "url": "https://example.com/captions.vtt"}]
            },
        },
    )
    monkeypatch.setattr(
        feed,
        "_download_caption_text",
        lambda track_url, session=None: (
            "WEBVTT\n\n"
            "00:00:00.000 --> 00:00:03.000\n"
            "The main topic in this environment is the Strait of Hormuz.\n\n"
            "00:00:03.000 --> 00:00:06.000\n"
            "The base case is we are treating this as a correction within the context of a secular bull market.\n\n"
            "00:00:06.000 --> 00:00:09.000\n"
            "XLK relative to SPY is over? The answer is no.\n\n"
            "00:00:09.000 --> 00:00:12.000\n"
            "The last thing it did was make a higher high.\n\n"
            "00:00:12.000 --> 00:00:15.000\n"
            "RSP relative to XLK still batting 0 for 5 monthly cloud.\n\n"
            "00:00:15.000 --> 00:00:18.000\n"
            "If we get a monthly close below the blue span, the odds of additional downside would increase.\n\n"
            "00:00:18.000 --> 00:00:21.000\n"
            "Have the long-term trends flipped in favor of XLF financials relative to XLK? Not yet.\n\n"
            "00:00:21.000 --> 00:00:24.000\n"
            "Dropping below the cloud here, especially if you get a monthly close below it, could potentially be significant.\n\n"
            "00:00:24.000 --> 00:00:27.000\n"
            "Tech FTEC relative to SPY tells us to keep an open mind about better than expected outcomes.\n\n"
            "00:00:27.000 --> 00:00:30.000\n"
            "This chart isn't screaming a major concern about a deflationary or traditional economic recession.\n"
        ),
    )

    artifact = feed.capture_ciovacco_feed(output_dir=tmp_path)

    latest_path = tmp_path / "ciovacco_latest.json"
    video_path = tmp_path / "6JCqUhMsPeM.json"
    transcript_path = tmp_path / "6JCqUhMsPeM_transcript.txt"
    preview_path = tmp_path / "ciovacco_latest_preview.html"

    assert latest_path.exists()
    assert video_path.exists()
    assert transcript_path.exists()
    assert preview_path.exists()
    assert artifact["latest_video"]["id"] == "6JCqUhMsPeM"
    assert artifact["observations"]["ratio_mentions"] == [
        {"ratio": "FTEC/SPY", "count": 1},
        {"ratio": "RSP/XLK", "count": 1},
        {"ratio": "XLF/XLK", "count": 1},
        {"ratio": "XLK/SPY", "count": 1},
    ]
    assert artifact["analysis"]["core_conclusion"].startswith("Base case")
    assert artifact["analysis"]["ratio_signals"][0]["ratio"]
    assert artifact["schedule"]["primary_run"] == "Saturday 14:00 HKT"
    assert artifact["schedule"]["recheck_run"] == "Sunday 14:00 HKT"

    saved = json.loads(latest_path.read_text(encoding="utf-8"))
    assert saved["latest_video"]["title"].startswith("WAR:")
    assert "Strait of Hormuz" in transcript_path.read_text(encoding="utf-8")
    assert "Core Conclusion" in preview_path.read_text(encoding="utf-8")


def test_scrape_ciovacco_main_supports_video_override(monkeypatch):
    calls: dict[str, object] = {}

    def _fake_capture(*, output_dir=None, channel_id=None, video_url=None, session=None):
        calls["output_dir"] = output_dir
        calls["channel_id"] = channel_id
        calls["video_url"] = video_url
        return {"latest_video": {"id": "abc123"}}

    monkeypatch.setattr(scrape_ciovacco, "capture_ciovacco_feed", _fake_capture)

    rc = scrape_ciovacco.main(
        [
            "--video-url",
            "https://www.youtube.com/watch?v=abc123",
            "--output-dir",
            "scraped_data/ciovacco-test",
        ]
    )

    assert rc == 0
    assert calls["video_url"] == "https://www.youtube.com/watch?v=abc123"
    assert calls["output_dir"] == "scraped_data/ciovacco-test"


def test_schedule_metadata_matches_requested_weekend_runs():
    assert feed.schedule_metadata() == {
        "primary_run": "Saturday 14:00 HKT",
        "recheck_run": "Sunday 14:00 HKT",
    }


def test_run_ciovacco_wrapper_uses_scrape_entrypoint():
    wrapper = (Path(__file__).resolve().parents[1] / "run_ciovacco_weekly.bat").read_text(encoding="utf-8")

    assert "python scrape_ciovacco.py" in wrapper


def test_register_ciovacco_weekly_task_has_both_weekend_triggers():
    script = (
        Path(__file__).resolve().parents[1] / "register_ciovacco_weekly_task.ps1"
    ).read_text(encoding="utf-8")

    assert "Saturday" in script
    assert "Sunday" in script
    assert "2:00PM" in script


def test_persist_ciovacco_artifact_writes_notebooklm_snapshot(tmp_path: Path):
    artifact = {
        "latest_video": {"id": "6JCqUhMsPeM", "title": "WAR:", "url": "https://www.youtube.com/watch?v=6JCqUhMsPeM"},
        "transcript": {"kind": "automatic_captions"},
        "analysis": {
            "core_conclusion": "Base case",
            "situation": "Situation",
            "posture": "Measured",
            "practical_action": "Action",
            "watch_items": ["Watch close"],
            "ratio_signals": [],
        },
        "notebooklm": {
            "notebook_id": "nb-123",
            "summary": "Historical summary",
            "questions": {"core_thesis": {"question": "Q", "answer": "A", "conversation_id": "c"}},
        },
    }

    saved = feed.persist_ciovacco_artifact(artifact, output_dir=tmp_path)

    assert (tmp_path / "ciovacco_latest.json").exists()
    assert (tmp_path / "6JCqUhMsPeM.json").exists()
    assert (tmp_path / "ciovacco_notebooklm_latest.json").exists()
    assert saved["preview"]["html_path"]


def test_scrape_ciovacco_main_syncs_notebooklm_when_requested(monkeypatch):
    artifact = {
        "latest_video": {
            "id": "abc123",
            "title": "Test video",
            "url": "https://www.youtube.com/watch?v=abc123",
        },
        "transcript": {"kind": "automatic_captions"},
        "analysis": {
            "core_conclusion": "Base case",
            "situation": "Situation",
            "posture": "Measured",
            "practical_action": "Action",
            "watch_items": [],
            "ratio_signals": [],
        },
    }
    calls: dict[str, object] = {}

    monkeypatch.setattr(scrape_ciovacco, "capture_ciovacco_feed", lambda **kwargs: artifact)
    monkeypatch.setattr(
        scrape_ciovacco,
        "resolve_notebooklm_sync_config",
        lambda **kwargs: {"notebook_id": "nb-123", "storage_path": "C:/state.json"},
    )
    monkeypatch.setattr(
        scrape_ciovacco,
        "run_notebooklm_sync",
        lambda payload, **kwargs: {"summary": "Notebook summary", "notebook_id": "nb-123"},
    )
    monkeypatch.setattr(
        scrape_ciovacco,
        "persist_ciovacco_artifact",
        lambda payload, output_dir=None: calls.setdefault("persisted", payload) or payload,
    )

    rc = scrape_ciovacco.main(["--sync-notebooklm", "--notebook-id", "nb-123"])

    assert rc == 0
    assert calls["persisted"]["notebooklm"]["summary"] == "Notebook summary"
