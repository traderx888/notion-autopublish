from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ciovacco.notebooklm_sync import (
    build_ciovacco_notebooklm_questions,
    find_source_by_url,
    resolve_notebooklm_sync_config,
    sync_ciovacco_notebooklm,
)


def _artifact() -> dict:
    return {
        "latest_video": {
            "id": "6JCqUhMsPeM",
            "title": "WAR: How To Handle A Correction That Morphs Into A 20-50% Drawdown",
            "url": "https://www.youtube.com/watch?v=6JCqUhMsPeM",
        },
        "analysis": {
            "core_conclusion": "Base case: correction inside secular bull unless guideposts fail.",
            "situation": "War and Strait of Hormuz risk remain the main issue.",
            "ratio_signals": [
                {"ratio": "XLK/SPY", "signal": "Tech leadership intact."},
                {"ratio": "RSP/XLK", "signal": "Broadening unconfirmed."},
                {"ratio": "XLF/XLK", "signal": "Financials not yet taking over."},
            ],
        },
    }


def test_resolve_notebooklm_sync_config_uses_explicit_then_env():
    config = resolve_notebooklm_sync_config(
        notebook_id="explicit-id",
        storage_path="C:/state.json",
        env={"CIOVACCO_NOTEBOOKLM_NOTEBOOK_ID": "env-id"},
    )

    assert config["notebook_id"] == "explicit-id"
    assert config["storage_path"] == "C:/state.json"

    env_config = resolve_notebooklm_sync_config(
        env={
            "CIOVACCO_NOTEBOOKLM_NOTEBOOK_ID": "env-id",
            "NOTEBOOKLM_STORAGE_PATH": "C:/env-state.json",
        }
    )

    assert env_config["notebook_id"] == "env-id"
    assert env_config["storage_path"] == "C:/env-state.json"


def test_build_ciovacco_notebooklm_questions_uses_artifact_context():
    questions = build_ciovacco_notebooklm_questions(_artifact())

    assert set(questions) == {"core_thesis", "what_changed", "ratio_logic", "action_items"}
    assert "6JCqUhMsPeM" in questions["what_changed"]
    assert "XLK/SPY, RSP/XLK, XLF/XLK" in questions["ratio_logic"]
    assert "secular bull" in questions["core_thesis"].lower()


def test_find_source_by_url_matches_canonical_youtube_url():
    sources = [
        SimpleNamespace(
            id="source-1",
            title="Ciovacco prior update",
            url="https://www.youtube.com/watch?v=6JCqUhMsPeM",
            kind="youtube",
            status=1,
        )
    ]

    matched = find_source_by_url(
        sources,
        "https://www.youtube.com/watch?v=6JCqUhMsPeM&t=2s",
    )

    assert matched is not None
    assert matched.id == "source-1"


def test_sync_ciovacco_notebooklm_reuses_existing_source_and_shapes_payload():
    artifact = _artifact()
    existing_source = SimpleNamespace(
        id="source-1",
        title="WAR: existing source",
        url="https://www.youtube.com/watch?v=6JCqUhMsPeM",
        kind=SimpleNamespace(value="youtube"),
        status=1,
    )

    class FakeNotebooks:
        async def get(self, notebook_id: str):
            return SimpleNamespace(id=notebook_id, title="Ciovacco DB")

        async def get_summary(self, notebook_id: str):
            return "Historical notebook summary"

    class FakeSources:
        def __init__(self):
            self.added = False

        async def list(self, notebook_id: str):
            return [existing_source]

        async def add_url(self, notebook_id: str, url: str, wait: bool = False):
            self.added = True
            return existing_source

        async def wait_until_ready(self, notebook_id: str, source_id: str, timeout: float = 120.0):
            return existing_source

    class FakeChat:
        async def ask(self, notebook_id: str, question: str, source_ids=None, conversation_id=None):
            return SimpleNamespace(answer=f"Answer for: {question[:24]}", conversation_id="conv-1")

    class FakeClient:
        def __init__(self):
            self.notebooks = FakeNotebooks()
            self.sources = FakeSources()
            self.chat = FakeChat()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_client_factory(storage_path: str | None):
        assert storage_path == "C:/state.json"
        return FakeClient()

    payload = asyncio.run(
        sync_ciovacco_notebooklm(
            artifact,
            notebook_id="99e260ac-3813-4c85-9eee-c05bd3f57b50",
            storage_path="C:/state.json",
            client_factory=fake_client_factory,
        )
    )

    assert payload["notebook_id"] == "99e260ac-3813-4c85-9eee-c05bd3f57b50"
    assert payload["notebook_title"] == "Ciovacco DB"
    assert payload["summary"] == "Historical notebook summary"
    assert payload["source"]["id"] == "source-1"
    assert payload["source"]["source_added"] is False
    assert set(payload["questions"]) == {"core_thesis", "what_changed", "ratio_logic", "action_items"}
    assert payload["questions"]["core_thesis"]["answer"].startswith("Answer for:")
