"""Tests for notebooklm_research.research_sync — core async research flow."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notebooklm_research.research_sync import (
    _canonicalize_youtube_url,
    _find_source_by_url,
    research_ticker,
    run_research_batch,
)


# ── URL canonicalization ──────────────────────────────────────


def test_canonicalize_standard_url():
    url = "https://www.youtube.com/watch?v=abc123&t=2s"
    assert _canonicalize_youtube_url(url) == "https://www.youtube.com/watch?v=abc123"


def test_canonicalize_short_url():
    url = "https://youtu.be/abc123"
    assert _canonicalize_youtube_url(url) == "https://www.youtube.com/watch?v=abc123"


def test_canonicalize_non_youtube():
    url = "https://example.com/article"
    assert _canonicalize_youtube_url(url) == "https://example.com/article"


# ── Source dedup ──────────────────────────────────────────────


def test_find_source_by_url_matches():
    sources = [
        SimpleNamespace(id="s1", url="https://www.youtube.com/watch?v=abc123"),
        SimpleNamespace(id="s2", url="https://www.youtube.com/watch?v=def456"),
    ]
    found = _find_source_by_url(sources, "https://youtu.be/abc123")
    assert found is not None
    assert found.id == "s1"


def test_find_source_by_url_no_match():
    sources = [SimpleNamespace(id="s1", url="https://www.youtube.com/watch?v=abc123")]
    assert _find_source_by_url(sources, "https://www.youtube.com/watch?v=xyz") is None


# ── Fake NotebookLM client ────────────────────────────────────


class FakeNotebooks:
    def __init__(self):
        self._notebooks = {}

    async def get(self, notebook_id: str):
        if notebook_id in self._notebooks:
            return self._notebooks[notebook_id]
        raise Exception(f"Notebook {notebook_id} not found")

    async def create(self, title: str):
        nb = SimpleNamespace(id=f"nb-{len(self._notebooks)}", title=title)
        self._notebooks[nb.id] = nb
        return nb


class FakeSources:
    def __init__(self, existing: list | None = None):
        self._existing = existing or []
        self.added_urls: list[str] = []

    async def list(self, notebook_id: str):
        return self._existing

    async def add_url(self, notebook_id: str, url: str, wait: bool = False):
        self.added_urls.append(url)
        return SimpleNamespace(id=f"src-{len(self.added_urls)}")

    async def wait_until_ready(self, notebook_id: str, source_id: str, timeout: float = 120.0):
        return SimpleNamespace(id=source_id, status="ready")


class FakeChat:
    async def ask(self, notebook_id: str, question: str, source_ids=None, conversation_id=None):
        return SimpleNamespace(
            answer=f"Research answer for: {question[:40]}",
            conversation_id="conv-1",
        )


class FakeClient:
    def __init__(self, existing_sources=None):
        self.notebooks = FakeNotebooks()
        self.sources = FakeSources(existing_sources)
        self.chat = FakeChat()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


# ── research_ticker ───────────────────────────────────────────


@patch("notebooklm_research.research_sync.search_ticker_videos")
def test_research_ticker_creates_notebook_and_asks_questions(mock_search, tmp_path: Path):
    mock_search.return_value = [
        {"url": "https://www.youtube.com/watch?v=vid1", "id": "vid1",
         "title": "XENE Earnings", "channel": "AnalystTV",
         "upload_date": "20260315", "duration": 600, "view_count": 5000,
         "description": "test"},
    ]

    client = FakeClient()
    registry = {}
    reg_path = tmp_path / "registry.json"
    output_dir = tmp_path / "output"

    target = {
        "ticker": "XENE",
        "source": "stockbee_ep",
        "grade": "SUPER_SWAN",
        "is_golden": True,
        "gap_pct": 43.37,
    }

    payload = asyncio.run(research_ticker(
        target,
        client=client,
        registry=registry,
        registry_path=reg_path,
        output_dir=output_dir,
    ))

    # Notebook created
    assert payload["notebook_id"].startswith("nb-")
    assert "XENE" in registry

    # Signal preserved
    assert payload["ticker"] == "XENE"
    assert payload["signal"]["source"] == "stockbee_ep"
    assert payload["signal"]["grade"] == "SUPER_SWAN"

    # YouTube source added
    assert len(payload["youtube_sources"]) == 1
    assert payload["youtube_sources"][0]["added"] is True

    # Questions answered (earnings set for EP source)
    assert "earnings_delta" in payload["questions"]
    assert "management_tone" in payload["questions"]
    assert payload["questions"]["earnings_delta"]["answer"].startswith("Research answer for:")

    # Output file written
    out_file = output_dir / "XENE_research.json"
    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["ticker"] == "XENE"


@patch("notebooklm_research.research_sync.search_ticker_videos")
def test_research_ticker_dedup_existing_source(mock_search, tmp_path: Path):
    mock_search.return_value = [
        {"url": "https://www.youtube.com/watch?v=existing1", "id": "existing1",
         "title": "Old Video", "channel": "Ch", "upload_date": "20260301",
         "duration": 300, "view_count": 100, "description": ""},
    ]

    existing_source = SimpleNamespace(
        id="src-old", url="https://www.youtube.com/watch?v=existing1",
    )
    client = FakeClient(existing_sources=[existing_source])
    registry = {}

    payload = asyncio.run(research_ticker(
        {"ticker": "NVDA", "source": "semianalysis", "context": "NVIDIA demand"},
        client=client,
        registry=registry,
        registry_path=tmp_path / "reg.json",
        output_dir=tmp_path / "out",
    ))

    # Source NOT added (already exists)
    assert payload["youtube_sources"][0]["added"] is False
    assert len(client.sources.added_urls) == 0


# ── run_research_batch ────────────────────────────────────────


@patch("notebooklm_research.research_sync.search_ticker_videos")
def test_run_research_batch(mock_search, tmp_path: Path):
    mock_search.return_value = []  # No YouTube results

    completed_tickers = []

    def on_complete(payload):
        completed_tickers.append(payload["ticker"])

    async def fake_factory(storage_path):
        return FakeClient()

    targets = [
        {"ticker": "AAA", "source": "manual"},
        {"ticker": "BBB", "source": "manual"},
    ]

    results = asyncio.run(run_research_batch(
        targets,
        output_dir=tmp_path / "out",
        client_factory=fake_factory,
        on_ticker_complete=on_complete,
    ))

    assert len(results) == 2
    assert {r["ticker"] for r in results} == {"AAA", "BBB"}
    assert set(completed_tickers) == {"AAA", "BBB"}


def test_run_research_batch_empty_targets(tmp_path: Path):
    results = asyncio.run(run_research_batch(
        [],
        output_dir=tmp_path / "out",
    ))
    assert results == []
