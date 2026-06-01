import json
from pathlib import Path

from tools.jarvis_memory_capsules import export_memory_capsules


def test_export_memory_capsules_writes_jsonl_artifact(tmp_path: Path):
    inbox = tmp_path / "inbox"
    output_path = tmp_path / "scraped_data" / "jarvis_memory" / "memory_capsules_latest.jsonl"
    inbox.mkdir()
    (inbox / "liquidity.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-13T10:00:00+08:00",
                "source_tool": "claude-web",
                "topic": "liquidity research",
                "tickers": ["SPY"],
                "summary": "Liquidity impulse improved before breadth.",
                "evidence": [{"title": "paper", "quote": "liquidity led breadth"}],
                "confidence": 0.8,
            }
        ),
        encoding="utf-8",
    )

    report = export_memory_capsules(inbox, output_path)

    assert report["accepted_count"] == 1
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["id"].startswith("claude-web:")
    assert rows[0]["topic"] == "liquidity research"


def test_export_memory_capsules_redacts_secrets(tmp_path: Path):
    inbox = tmp_path / "inbox"
    output_path = tmp_path / "memory_capsules_latest.jsonl"
    inbox.mkdir()
    (inbox / "secret.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-13T10:00:00+08:00",
                "source_tool": "chatgpt-web",
                "topic": "secret check",
                "summary": "DISCORD_BOT_TOKEN=abc123 should never leak.",
                "evidence": ["OpenAI token sk-secretvalue should be hidden."],
            }
        ),
        encoding="utf-8",
    )

    export_memory_capsules(inbox, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert "abc123" not in text
    assert "sk-secretvalue" not in text
    assert "[REDACTED]" in text
