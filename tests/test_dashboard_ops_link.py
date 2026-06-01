from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_public_dashboard_contains_local_ops_pointer_without_live_internal_state():
    html = (REPO_ROOT / "output" / "dashboard.html").read_text(encoding="utf-8")

    assert "External Scrapers Ops" in html
    assert "127.0.0.1:8765" in html
    assert "ceremony_stamp.json" not in html
    assert "/api/status" not in html
