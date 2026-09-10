"""Tests for the bounded Codex newsletter synthesis adapter."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from tools import codex_synthesis


def test_extract_json_object_from_plain_or_fenced_output():
    assert codex_synthesis._extract_json_object('{"title": "ok"}') == {
        "title": "ok"
    }
    assert codex_synthesis._extract_json_object(
        'Result follows:\n```json\n{"title": "ok"}\n```'
    ) == {"title": "ok"}


def test_synthesize_json_uses_bounded_codex_command(monkeypatch):
    observed: dict = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text(
            '{"title_zh": "測試"}', encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(codex_synthesis.subprocess, "run", fake_run)

    result = codex_synthesis.synthesize_json("PROMPT", model="gpt-5.6-sol")

    assert result == {"title_zh": "測試"}
    command = observed["command"]
    assert command[:2] == ["codex", "exec"]
    assert "claude" not in command
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[-1] == "-"
    assert observed["kwargs"]["input"] == "PROMPT"
    assert observed["kwargs"]["check"] is False


def test_synthesize_json_fails_closed_on_cli_error(monkeypatch):
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="auth failed")

    monkeypatch.setattr(codex_synthesis.subprocess, "run", fake_run)

    assert codex_synthesis.synthesize_json("PROMPT") is None


def test_synthesize_json_fails_closed_on_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(codex_synthesis.subprocess, "run", fake_run)

    assert codex_synthesis.synthesize_json("PROMPT") is None


def test_newsletter_delegates_to_codex_adapter(tmp_path, monkeypatch):
    from tools import bloomberg_newsletter_build as newsletter

    article_path = tmp_path / "article.md"
    article_path.write_text("# Article\n\nSource text", encoding="utf-8")
    observed: dict = {}

    def fake_synthesize(prompt, **kwargs):
        observed["prompt"] = prompt
        observed["kwargs"] = kwargs
        return {"title_zh": "測試"}

    monkeypatch.setattr(newsletter, "synthesize_json", fake_synthesize)
    articles = [
        {
            "title": "Article",
            "mdPath": str(article_path),
            "topics": ["rates"],
        }
    ]

    result = newsletter.synthesize_with_codex(["rates"], articles)

    assert result == {"title_zh": "測試"}
    assert "Source text" in observed["prompt"]
    assert "newsletter (1 articles)" == observed["kwargs"]["label"]


def test_weekly_digest_delegates_to_codex_adapter(tmp_path, monkeypatch):
    from tools import bloomberg_weekly_digest as digest

    article_path = tmp_path / "article.md"
    article_path.write_text("# Article\n\nSource text", encoding="utf-8")
    observed: dict = {}

    def fake_synthesize(prompt, **kwargs):
        observed["prompt"] = prompt
        observed["kwargs"] = kwargs
        return {"title_zh": "週報"}

    monkeypatch.setattr(codex_synthesis, "synthesize_json", fake_synthesize)
    groups = {
        "rates": [
            {
                "title": "Article",
                "mdPath": str(article_path),
                "topics": ["rates"],
            }
        ]
    }

    result = digest._synthesize_digest(groups)

    assert result == {"title_zh": "週報"}
    assert "Source text" in observed["prompt"]
    assert "weekly digest (1 articles across 1 topics)" == observed["kwargs"]["label"]
