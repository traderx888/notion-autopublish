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


def test_extract_pdf_happy_path(tmp_path, monkeypatch):
    fake = tmp_path / "BOFA Hartnett Flow Show #equities #ai.pdf"
    fake.write_bytes(b"%PDF-1.4 stub")  # real bytes don't matter; we stub the readers

    def fake_extract_pdf_text(path):
        return ("Header noise\n"
                "Page 1 of 8\n"
                "Real article body line one.\n"
                "Real article body line two.\n")

    monkeypatch.setattr("tools.bloomberg_pdf_convert.extract_pdf_text", fake_extract_pdf_text)

    out = mod.extract_pdf(fake, 200)
    assert out["error"] is None
    assert "Real article body line one" in out["body"]
    assert "Page 1 of 8" not in out["body"]  # disclaimer scrubber ran
    assert out["topics"] == ["equities", "ai"]
    assert out["title"] == "BOFA Hartnett Flow Show"


def test_extract_pdf_truncates_body(tmp_path, monkeypatch):
    fake = tmp_path / "big.pdf"
    fake.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "tools.bloomberg_pdf_convert.extract_pdf_text",
        lambda p: "abcdef" * 1000,
    )
    out = mod.extract_pdf(fake, n_chars := 50)
    assert out["error"] is None
    assert len(out["body"]) == n_chars


def test_extract_pdf_extract_failure_is_non_fatal(tmp_path, monkeypatch):
    fake = tmp_path / "broken.pdf"
    fake.write_bytes(b"not a real pdf")

    def boom(path):
        raise ValueError("malformed pdf")

    monkeypatch.setattr("tools.bloomberg_pdf_convert.extract_pdf_text", boom)
    out = mod.extract_pdf(fake, 100)
    assert out["body"] == ""
    assert "malformed pdf" in out["error"]
    assert out["title"] == "broken"


def test_render_bundle_uses_pdf_extractor(tmp_path, monkeypatch):
    pdf = tmp_path / "Article #china.pdf"
    pdf.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(
        "tools.bloomberg_pdf_convert.extract_pdf_text",
        lambda p: "PBoC liquidity slumped in April per daily data.",
    )
    hits = [{
        "path": pdf,
        "rel": "Article #china.pdf",
        "mtime": datetime.now(timezone.utc),
        "size": pdf.stat().st_size,
    }]
    now = datetime.now(timezone.utc)
    out = mod.render_bundle(tmp_path, now - timedelta(days=1), now, hits)
    assert "PBoC liquidity slumped" in out
    assert "tags: #china" in out
    assert "title: Article" in out


def test_render_bundle_skips_pdf_body_over_size_cap(tmp_path, monkeypatch):
    pdf = tmp_path / "huge.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    called = {"n": 0}

    def fake_extract(p):
        called["n"] += 1
        return "should not appear"

    monkeypatch.setattr("tools.bloomberg_pdf_convert.extract_pdf_text", fake_extract)
    hits = [{
        "path": pdf,
        "rel": "huge.pdf",
        "mtime": datetime.now(timezone.utc),
        "size": mod.PDF_MAX_BYTES + 1,
    }]
    now = datetime.now(timezone.utc)
    out = mod.render_bundle(tmp_path, now - timedelta(days=1), now, hits)
    assert called["n"] == 0
    assert "huge.pdf" in out
    assert "should not appear" not in out


