from __future__ import annotations

import json
from pathlib import Path

from liquidity_tracker import run_liquidity_tracker


def test_run_liquidity_tracker_writes_sidecars(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    raw_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(raw_dir))
    monkeypatch.setenv("LIQUIDITY_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("LIQUIDITY_CHECKER_CONFIG", str(tmp_path / "missing.local.json"))
    monkeypatch.setattr(
        "liquidity_tracker.capture_latest_h_model",
        lambda *args, **kwargs: {
            "available": True,
            "captured_at": "2026-03-09T12:00:00+00:00",
            "screenshot_path": str(raw_dir / "h_model_latest_screenshot.png"),
            "articles": [
                {
                    "url": "https://capitalwars.substack.com/p/post",
                    "title": "Liquidity Support",
                    "date": "2026-03-09T10:00:00+00:00",
                    "body_text": "US liquidity is improving and repo stress is easing.",
                }
            ],
            "capture_status": "ok",
        },
    )

    result = run_liquidity_tracker()

    assert result["composite"]["regime"] == "EXPANDING"
    assert (output_dir / "h_model_latest.json").exists()
    assert (output_dir / "liquidity_tracker_latest.json").exists()
    assert (output_dir / "liquidity_tracker_history.csv").exists()
    saved = json.loads((output_dir / "liquidity_tracker_latest.json").read_text(encoding="utf-8"))
    assert saved["status"]["internal_checker"] in {"missing", "partial"}


def test_run_liquidity_tracker_can_skip_h_capture(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    raw_dir.mkdir()
    output_dir.mkdir()
    (raw_dir / "h_model_latest_raw.json").write_text(
        json.dumps(
            {
                "captured_at": "2026-03-09T12:00:00+00:00",
                "articles": [
                    {
                        "url": "https://capitalwars.substack.com/p/post",
                        "title": "Liquidity Support",
                        "date": "2026-03-09T10:00:00+00:00",
                        "body_text": "US liquidity is improving and repo stress is easing.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(raw_dir))
    monkeypatch.setenv("LIQUIDITY_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("LIQUIDITY_CHECKER_CONFIG", str(tmp_path / "missing.local.json"))

    result = run_liquidity_tracker(skip_h_capture=True)

    assert result["status"]["h_model_capture"] in {"ok", "carry_forward"}


def test_run_liquidity_tracker_can_skip_internal_checker(tmp_path: Path, monkeypatch):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    raw_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(raw_dir))
    monkeypatch.setenv("LIQUIDITY_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("LIQUIDITY_CHECKER_CONFIG", str(tmp_path / "missing.local.json"))
    monkeypatch.setattr(
        "liquidity_tracker.capture_latest_h_model",
        lambda *args, **kwargs: {
            "available": True,
            "captured_at": "2026-03-09T12:00:00+00:00",
            "screenshot_path": str(raw_dir / "h_model_latest_screenshot.png"),
            "articles": [
                {
                    "url": "https://capitalwars.substack.com/p/post",
                    "title": "Liquidity Support",
                    "date": "2026-03-09T10:00:00+00:00",
                    "body_text": "US liquidity is improving and repo stress is easing.",
                }
            ],
            "capture_status": "ok",
        },
    )

    result = run_liquidity_tracker(skip_internal_checker=True)

    assert result["status"]["internal_checker"] == "missing"
