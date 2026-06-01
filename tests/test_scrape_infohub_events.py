"""Unit tests for scrape_infohub_events CLI.

Stubs the InfoHubClient so the CLI can be exercised without a real Info
Hub install. Covers:
  - Happy-path output shape with filtered + deduped items.
  - Error-per-source is captured but doesn't crash the run.
  - Item filtering matches query_marker lineage AND title tokens.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


class _StubClient:
    """Minimal InfoHubClient stand-in for CLI tests."""

    def __init__(self, *, items_by_source: dict, fail_sources: set | None = None, **kwargs):
        self._items = items_by_source
        self._fail = fail_sources or set()
        self.crawl_calls: list[tuple] = []

    def crawl_run(self, source, keywords, *, days, max_items):
        if source in self._fail:
            from infohub_research.bridge import InfoHubError
            raise InfoHubError(f"boom {source}")
        self.crawl_calls.append((source, tuple(keywords), days, max_items))
        return {"source": source, "items": len(self._items.get(source, []))}

    def items_latest(self, source, *, limit):
        return list(self._items.get(source, []))[:limit]


@pytest.fixture(autouse=True)
def _cleanup_module():
    yield
    sys.modules.pop("scrape_infohub_events", None)


def _run_cli(monkeypatch, tmp_path, events, items_by_source, fail_sources=None,
             sources="cnbc_search,bbc_search"):
    events_path = tmp_path / "events.json"
    events_path.write_text(json.dumps(events), encoding="utf-8")
    out_path = tmp_path / "out.json"

    # Build the stub client and patch the constructor.
    def _factory(**kwargs):
        return _StubClient(
            items_by_source=items_by_source,
            fail_sources=fail_sources,
        )

    import infohub_research.bridge as bridge_mod
    monkeypatch.setattr(bridge_mod, "InfoHubClient", _factory)

    monkeypatch.setattr(sys, "argv", [
        "scrape_infohub_events.py",
        "--events-json", str(events_path),
        "--output", str(out_path),
        "--sources", sources,
        "--days", "1",
        "--max-items-per-source", "3",
    ])

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(REPO_ROOT / "scrape_infohub_events.py"), run_name="__main__")
    assert exc.value.code == 0

    return json.loads(out_path.read_text(encoding="utf-8"))


def _mk_item(*, title, url, publish_time, query_marker=""):
    return {
        "title": title,
        "url": url,
        "publish_time": publish_time,
        "fetched_at": "2026-04-08T10:00:00+00:00",
        "lineage_json": json.dumps({"query_marker": query_marker}),
    }


def test_happy_path_output_shape(monkeypatch, tmp_path):
    events = [
        {"name": "FOMC Meeting Minutes", "time_hkt": "02:00",
         "forecast": "", "previous": ""},
    ]
    items = {
        "cnbc_search": [
            _mk_item(
                title="Fed minutes show divided FOMC on rate cuts",
                url="https://cnbc.com/a",
                publish_time="2026-04-08 09:00:00",
                query_marker="FOMC Meeting Minutes",
            ),
            _mk_item(
                title="Unrelated tech story",
                url="https://cnbc.com/b",
                publish_time="2026-04-08 08:00:00",
            ),
        ],
        "bbc_search": [
            _mk_item(
                title="Powell signals caution ahead of FOMC minutes",
                url="https://bbc.com/a",
                publish_time="2026-04-08 07:00:00",
                query_marker="FOMC Meeting Minutes",
            ),
        ],
    }

    payload = _run_cli(monkeypatch, tmp_path, events, items)

    assert payload["sources_tried"] == ["cnbc_search", "bbc_search"]
    assert len(payload["events"]) == 1
    event = payload["events"][0]
    assert event["name"] == "FOMC Meeting Minutes"
    # "Unrelated tech story" should be filtered out; the two lineage matches remain.
    urls = {item["url"] for item in event["items"]}
    assert urls == {"https://cnbc.com/a", "https://bbc.com/a"}
    # Sorted newest first.
    assert event["items"][0]["publish_time"] == "2026-04-08 09:00:00"
    assert event["errors"] == {}


def test_source_error_captured_not_fatal(monkeypatch, tmp_path):
    events = [{"name": "Crude Oil Inventories", "time_hkt": "22:30",
               "forecast": "1.08M", "previous": "6.41M"}]
    items = {
        "cnbc_search": [
            _mk_item(
                title="Crude oil inventories rise as traders watch",
                url="https://cnbc.com/oil",
                publish_time="2026-04-08 06:00:00",
            ),
        ],
        "bbc_search": [],
    }
    payload = _run_cli(
        monkeypatch, tmp_path, events, items,
        fail_sources={"bbc_search"},
    )
    event = payload["events"][0]
    assert len(event["items"]) == 1
    assert "bbc_search" in event["errors"]
    assert "boom" in event["errors"]["bbc_search"]


def test_title_token_match_fallback(monkeypatch, tmp_path):
    """When query_marker is missing, we still match via title tokens."""
    events = [{"name": "10-Year Note Auction", "time_hkt": "01:00",
               "forecast": "", "previous": "4.217%"}]
    items = {
        "cnbc_search": [
            _mk_item(
                title="Treasury auction: 10-Year Note demand softens",
                url="https://cnbc.com/auction",
                publish_time="2026-04-08 05:00:00",
                query_marker="",  # no lineage marker → must match via tokens
            ),
            _mk_item(
                title="Bitcoin hits new high",
                url="https://cnbc.com/btc",
                publish_time="2026-04-08 04:00:00",
            ),
        ],
        "bbc_search": [],
    }
    payload = _run_cli(monkeypatch, tmp_path, events, items)
    event = payload["events"][0]
    assert len(event["items"]) == 1
    assert event["items"][0]["url"] == "https://cnbc.com/auction"


def test_url_dedupe_across_sources(monkeypatch, tmp_path):
    events = [{"name": "FOMC Meeting Minutes", "time_hkt": "02:00",
               "forecast": "", "previous": ""}]
    same_url = "https://newswire.example/a"
    items = {
        "cnbc_search": [
            _mk_item(title="Fed minutes released", url=same_url,
                     publish_time="2026-04-08 09:00:00",
                     query_marker="FOMC Meeting Minutes"),
        ],
        "bbc_search": [
            _mk_item(title="Fed minutes released", url=same_url,
                     publish_time="2026-04-08 09:00:00",
                     query_marker="FOMC Meeting Minutes"),
        ],
    }
    payload = _run_cli(monkeypatch, tmp_path, events, items)
    event = payload["events"][0]
    assert len(event["items"]) == 1
