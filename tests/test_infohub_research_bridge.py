"""Unit tests for infohub_research.bridge.InfoHubClient."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import infohub_research.bridge as bridge_mod
from infohub_research.bridge import InfoHubClient, InfoHubError


@pytest.fixture
def fake_install(tmp_path: Path) -> Path:
    root = tmp_path / "Info Hub"
    (root / ".venv" / "Scripts").mkdir(parents=True)
    py = root / ".venv" / "Scripts" / "python.exe"
    py.write_text("", encoding="utf-8")
    return root


def _make_proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_discovery_uses_explicit_dir(fake_install: Path):
    client = InfoHubClient(infohub_dir=str(fake_install))
    assert client.root == fake_install.resolve()
    assert client.python.name == "python.exe"


def test_discovery_failure(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("INFOHUB_DIR", raising=False)
    # Point hardcoded fallback at a nonexistent path so discovery fails.
    monkeypatch.setattr(bridge_mod, "_DEFAULT_FALLBACK", tmp_path / "absent")
    with pytest.raises(InfoHubError):
        InfoHubClient(infohub_dir=str(tmp_path / "missing"))


def test_run_passes_utf8_env_and_parses_json(fake_install: Path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        captured["cwd"] = kwargs.get("cwd")
        return _make_proc(0, stdout=json.dumps([{"key": "bbc"}]))

    monkeypatch.setattr(bridge_mod.subprocess, "run", fake_run)
    client = InfoHubClient(infohub_dir=str(fake_install))
    result = client.health_check()
    assert result is True
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"
    assert captured["cmd"][1:4] == ["-m", "app.cli", "sources"]
    assert captured["cwd"] == str(fake_install.resolve())


def test_activate_profile_builds_flags(fake_install: Path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _make_proc(0, stdout=json.dumps({"profile_key": "abc", "id": 1}))

    monkeypatch.setattr(bridge_mod.subprocess, "run", fake_run)
    client = InfoHubClient(infohub_dir=str(fake_install))
    out = client.activate_profile({
        "name": "Test",
        "domain": "finance",
        "theme": "equities",
        "focus": "earnings reset",
        "queries": ["NVDA", "earnings"],
        "sources": ["bbc_search", "cnbc_search"],
        "priority": 50,
    })
    assert out["profile_key"] == "abc"
    cmd = captured["cmd"]
    assert "watch-profiles" in cmd
    assert "activate" in cmd
    # Comma-joined lists
    qi = cmd.index("--queries")
    assert cmd[qi + 1] == "NVDA,earnings"
    si = cmd.index("--sources")
    assert cmd[si + 1] == "bbc_search,cnbc_search"
    pi = cmd.index("--priority")
    assert cmd[pi + 1] == "50"


def test_crawl_run_returns_dict(fake_install: Path, monkeypatch):
    monkeypatch.setattr(bridge_mod.subprocess, "run",
                        lambda *a, **k: _make_proc(0, stdout=json.dumps({"items": 5})))
    client = InfoHubClient(infohub_dir=str(fake_install))
    out = client.crawl_run("bbc_search", ["oil tanker"], days=2, max_items=3)
    assert out == {"items": 5}


def test_items_latest_returns_list(fake_install: Path, monkeypatch):
    monkeypatch.setattr(bridge_mod.subprocess, "run",
                        lambda *a, **k: _make_proc(0, stdout=json.dumps([{"id": 1}, {"id": 2}])))
    client = InfoHubClient(infohub_dir=str(fake_install))
    items = client.items_latest("bbc_search", limit=2)
    assert len(items) == 2


def test_nonzero_exit_raises_with_payload(fake_install: Path, monkeypatch):
    monkeypatch.setattr(bridge_mod.subprocess, "run",
                        lambda *a, **k: _make_proc(2, stdout="", stderr="boom"))
    client = InfoHubClient(infohub_dir=str(fake_install))
    with pytest.raises(InfoHubError) as exc:
        client.activate_profile({"name": "x", "domain": "finance",
                                  "theme": "equities", "focus": "earnings reset"})
    assert "boom" in exc.value.stderr


def test_timeout_wraps_to_infohub_error(fake_install: Path, monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1)
    monkeypatch.setattr(bridge_mod.subprocess, "run", boom)
    client = InfoHubClient(infohub_dir=str(fake_install))
    with pytest.raises(InfoHubError):
        client.crawl_run("bbc_search", ["x"])


def test_unparseable_json_raises(fake_install: Path, monkeypatch):
    monkeypatch.setattr(bridge_mod.subprocess, "run",
                        lambda *a, **k: _make_proc(0, stdout="not-json"))
    client = InfoHubClient(infohub_dir=str(fake_install))
    with pytest.raises(InfoHubError):
        client.activate_profile({"name": "x", "domain": "finance",
                                  "theme": "equities", "focus": "earnings reset"})
