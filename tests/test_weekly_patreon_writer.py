"""Tests for tools/weekly_patreon_writer.py — scope is the date-window scan,
bundle rendering, and CLI wiring. No network."""

from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "weekly_patreon_writer",
        Path(__file__).resolve().parents[1] / "tools" / "weekly_patreon_writer.py",
    )
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m


mod = _load_module()


def _touch(p: Path, *, mtime_days_ago: int, body: str = "") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    t = (datetime.now(timezone.utc) - timedelta(days=mtime_days_ago)).timestamp()
    os.utime(p, (t, t))
    return p


def test_collect_files_filters_by_window(tmp_path):
    _touch(tmp_path / "fresh.md", mtime_days_ago=1, body="hello")
    _touch(tmp_path / "old.md", mtime_days_ago=30, body="old")
    _touch(tmp_path / "future.md", mtime_days_ago=-2, body="future")

    now = datetime.now(timezone.utc)
    hits = mod.collect_files(
        tmp_path,
        now - timedelta(days=7),
        now + timedelta(days=1),
    )
    names = {h["rel"] for h in hits}
    assert names == {"fresh.md"}


def test_collect_files_skips_noise_dirs(tmp_path):
    _touch(tmp_path / ".git" / "HEAD", mtime_days_ago=0)
    _touch(tmp_path / "__pycache__" / "x.pyc", mtime_days_ago=0)
    _touch(tmp_path / "node_modules" / "pkg" / "index.js", mtime_days_ago=0)
    keep = _touch(tmp_path / "data" / "today.csv", mtime_days_ago=0)

    now = datetime.now(timezone.utc)
    hits = mod.collect_files(tmp_path, now - timedelta(days=1), now + timedelta(days=1))
    rels = {h["rel"] for h in hits}
    assert rels == {str(keep.relative_to(tmp_path))}


def test_collect_files_caps_at_max_files(tmp_path):
    for i in range(15):
        _touch(tmp_path / f"f{i:02d}.md", mtime_days_ago=i % 5)
    now = datetime.now(timezone.utc)
    hits = mod.collect_files(
        tmp_path,
        now - timedelta(days=30),
        now + timedelta(days=1),
        max_files=5,
    )
    assert len(hits) == 5
    # newest first
    for a, b in zip(hits, hits[1:]):
        assert a["mtime"] >= b["mtime"]


def test_render_bundle_embeds_text_head(tmp_path):
    p = _touch(tmp_path / "note.md", mtime_days_ago=0, body="# Title\n\nbody line")
    hits = [{
        "path": p,
        "rel": "note.md",
        "mtime": datetime.now(timezone.utc),
        "size": p.stat().st_size,
    }]
    out = mod.render_bundle(tmp_path, datetime.now(timezone.utc) - timedelta(days=1), datetime.now(timezone.utc), hits)
    assert "## `note.md`" in out
    assert "# Title" in out
    assert "body line" in out


def test_render_bundle_skips_body_for_non_text(tmp_path):
    p = _touch(tmp_path / "blob.bin", mtime_days_ago=0, body="garbage")
    hits = [{
        "path": p,
        "rel": "blob.bin",
        "mtime": datetime.now(timezone.utc),
        "size": p.stat().st_size,
    }]
    out = mod.render_bundle(tmp_path, datetime.now(timezone.utc) - timedelta(days=1), datetime.now(timezone.utc), hits)
    assert "blob.bin" in out
    assert "garbage" not in out  # binary: skip head


def test_main_writes_output_and_handles_missing_root(tmp_path, capsys):
    root = tmp_path / "nope"
    out = tmp_path / "bundle.md"
    rc = mod.main([
        "--root", str(root),
        "--out", str(out),
        "--since", "2026-01-01",
        "--until", "2026-01-02",
    ])
    assert rc == 0
    assert out.exists()
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_main_round_trip(tmp_path):
    root = tmp_path / "blp" / "data"
    _touch(root / "pdf" / "report.txt", mtime_days_ago=0, body="content")
    out = tmp_path / "bundle.md"
    now = datetime.now(timezone.utc)
    rc = mod.main([
        "--root", str(root),
        "--out", str(out),
        "--since", (now - timedelta(days=2)).strftime("%Y-%m-%d"),
        "--until", (now + timedelta(days=1)).strftime("%Y-%m-%d"),
    ])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "pdf" in text and "report.txt" in text
    assert "content" in text
