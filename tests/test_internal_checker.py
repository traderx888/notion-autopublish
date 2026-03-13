from __future__ import annotations

from pathlib import Path

import pandas as pd

from liquidity.internal_checker import (
    _resolve_tesseract_cmd,
    build_internal_checker_snapshot,
    load_internal_checker_inputs,
)


def test_load_internal_checker_inputs_supports_excel_directory_and_recursive_screenshots(tmp_path: Path):
    excel_dir = tmp_path / "bbg excel"
    excel_dir.mkdir()
    old_file = excel_dir / "W_01.xlsx"
    new_file = excel_dir / "W_02.xlsx"
    temp_lock = excel_dir / "~$W_03.xlsx"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")
    temp_lock.write_bytes(b"temp")

    screens_root = tmp_path / "Screenshots"
    march = screens_root / "2026-03"
    feb = screens_root / "2026-02"
    march.mkdir(parents=True)
    feb.mkdir(parents=True)
    older = feb / "older.png"
    latest = march / "latest.png"
    older.write_bytes(b"old")
    latest.write_bytes(b"new")

    config = {
        "excel": {
            "path": excel_dir,
            "glob": "W_*.xlsx",
        },
        "screenshot": {
            "dir": screens_root,
            "glob": "*.png",
            "recursive": True,
        },
    }

    import os
    os.utime(old_file, (1, 1))
    os.utime(new_file, (2, 2))
    os.utime(temp_lock, (3, 3))
    os.utime(older, (1, 1))
    os.utime(latest, (2, 2))

    inputs = load_internal_checker_inputs(config)

    assert inputs["excel_path"] == new_file
    assert inputs["screenshot_path"] == latest


def test_internal_checker_reads_excel_and_matches_ocr(tmp_path: Path, monkeypatch):
    excel_path = tmp_path / "checker.xlsx"
    screenshot_dir = tmp_path / "screens"
    screenshot_dir.mkdir()
    screenshot = screenshot_dir / "latest.png"
    screenshot.write_bytes(b"fake")

    pd.DataFrame(
        [
            {
                "Date": "2026-03-08",
                "LiquidityLevel": 98.0,
                "LiquidityMom5D": -0.8,
                "LiquidityMom20D": -1.6,
            }
        ]
    ).to_excel(excel_path, index=False, sheet_name="Liquidity")

    config = {
        "excel": {
            "path": excel_path,
            "sheet_name": "Liquidity",
            "date_column": "Date",
            "metrics": {
                "level": "LiquidityLevel",
                "mom_5d": "LiquidityMom5D",
                "mom_20d": "LiquidityMom20D",
            },
        },
        "screenshot": {
            "dir": screenshot_dir,
            "glob": "*.png",
            "ocr_patterns": {
                "repo_stress": "repo|SOFR",
                "risk_off": "risk off|cash",
                "liquidity_down": "liquidity.*peaking",
                "liquidity_up": "liquidity.*improving",
            },
        },
        "thresholds": {
            "mom_5d_positive": 0.5,
            "mom_5d_negative": -0.5,
            "mom_20d_positive": 1.5,
            "mom_20d_negative": -1.5,
            "urgent_alert_min_hits": 2,
        },
    }
    monkeypatch.setattr(
        "liquidity.internal_checker.ocr_image_to_text",
        lambda path: "Repo stress is rising. Liquidity is peaking. Risk off and cash.",
    )

    snapshot = build_internal_checker_snapshot(config, now_iso="2026-03-09T12:00:00+00:00")

    assert snapshot["available"] is True
    assert snapshot["ocr_available"] is True
    assert snapshot["series"]["mom_5d"] == -0.8
    assert snapshot["liquidity_direction"] == "CONTRACTING"
    assert snapshot["urgent_change"] is True
    assert "repo_stress" in snapshot["alert_hits"]


def test_internal_checker_works_without_ocr(tmp_path: Path, monkeypatch):
    excel_path = tmp_path / "checker.xlsx"
    screenshot_dir = tmp_path / "screens"
    screenshot_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Date": "2026-03-08",
                "LiquidityLevel": 101.0,
                "LiquidityMom5D": 0.7,
                "LiquidityMom20D": 1.9,
            }
        ]
    ).to_excel(excel_path, index=False, sheet_name="Liquidity")

    config = {
        "excel": {
            "path": excel_path,
            "sheet_name": "Liquidity",
            "date_column": "Date",
            "metrics": {
                "level": "LiquidityLevel",
                "mom_5d": "LiquidityMom5D",
                "mom_20d": "LiquidityMom20D",
            },
        },
        "screenshot": {
            "dir": screenshot_dir,
            "glob": "*.png",
            "ocr_patterns": {},
        },
        "thresholds": {
            "mom_5d_positive": 0.5,
            "mom_5d_negative": -0.5,
            "mom_20d_positive": 1.5,
            "mom_20d_negative": -1.5,
            "urgent_alert_min_hits": 2,
        },
    }
    monkeypatch.setattr(
        "liquidity.internal_checker.ocr_image_to_text",
        lambda path: (_ for _ in ()).throw(RuntimeError("ocr not available")),
    )

    snapshot = build_internal_checker_snapshot(config, now_iso="2026-03-09T12:00:00+00:00")

    assert snapshot["available"] is True
    assert snapshot["ocr_available"] is False
    assert snapshot["liquidity_direction"] == "EXPANDING"


def test_internal_checker_supports_row_selector_metrics(tmp_path: Path, monkeypatch):
    excel_path = tmp_path / "dashboard.xlsx"
    screenshot_dir = tmp_path / "screens"
    screenshot_dir.mkdir()
    (screenshot_dir / "latest.png").write_bytes(b"fake")

    pd.DataFrame(
        [
            {
                "Ticker": "China Monthly Money Supply M2",
                "Last Px (1 Year)": 9.0,
                "Net": 0.6,
                "%1M": 2.0,
            },
            {
                "Ticker": "United States SOFR Secured Ove",
                "Last Px (1 Year)": 3.67,
                "Net": -0.04,
                "%1M": -1.08,
            },
        ]
    ).to_excel(excel_path, index=False, sheet_name="Sheet 1")

    config = {
        "excel": {
            "path": excel_path,
            "sheet_name": "Sheet 1",
            "metrics": {
                "level": {
                    "match_column": "Ticker",
                    "match_text": "China Monthly Money Supply M2",
                    "value_column": "Last Px (1 Year)",
                },
                "mom_5d": {
                    "match_column": "Ticker",
                    "match_text": "China Monthly Money Supply M2",
                    "value_column": "Net",
                },
                "mom_20d": {
                    "match_column": "Ticker",
                    "match_text": "China Monthly Money Supply M2",
                    "value_column": "%1M",
                },
            },
        },
        "screenshot": {
            "dir": screenshot_dir,
            "glob": "*.png",
            "ocr_patterns": {},
        },
        "thresholds": {
            "mom_5d_positive": 0.5,
            "mom_5d_negative": -0.5,
            "mom_20d_positive": 1.5,
            "mom_20d_negative": -1.5,
            "urgent_alert_min_hits": 2,
        },
    }
    monkeypatch.setattr("liquidity.internal_checker.ocr_image_to_text", lambda path: "")

    snapshot = build_internal_checker_snapshot(config, now_iso="2026-03-09T12:00:00+00:00")

    assert snapshot["series"]["level"] == 9.0
    assert snapshot["series"]["mom_5d"] == 0.6
    assert snapshot["series"]["mom_20d"] == 2.0
    assert snapshot["liquidity_direction"] == "EXPANDING"


def test_internal_checker_supports_metric_multiplier(tmp_path: Path, monkeypatch):
    excel_path = tmp_path / "dashboard.xlsx"
    screenshot_dir = tmp_path / "screens"
    screenshot_dir.mkdir()
    (screenshot_dir / "latest.png").write_bytes(b"fake")

    pd.DataFrame(
        [
            {
                "Ticker": "United States SOFR Secured Ove",
                "%1D": -1.08,
                "%1M": 0.55,
                "Last Px (1 Year)": 3.67,
            },
        ]
    ).to_excel(excel_path, index=False, sheet_name="Sheet 1")

    config = {
        "excel": {
            "path": excel_path,
            "sheet_name": "Sheet 1",
            "metrics": {
                "level": {
                    "match_column": "Ticker",
                    "match_text": "United States SOFR Secured Ove",
                    "value_column": "Last Px (1 Year)",
                },
                "mom_5d": {
                    "match_column": "Ticker",
                    "match_text": "United States SOFR Secured Ove",
                    "value_column": "%1D",
                    "multiplier": -1,
                },
                "mom_20d": {
                    "match_column": "Ticker",
                    "match_text": "United States SOFR Secured Ove",
                    "value_column": "%1M",
                    "multiplier": -1,
                },
            },
        },
        "screenshot": {
            "dir": screenshot_dir,
            "glob": "*.png",
            "ocr_patterns": {},
        },
        "thresholds": {
            "mom_5d_positive": 0.5,
            "mom_5d_negative": -0.5,
            "mom_20d_positive": 1.5,
            "mom_20d_negative": -1.5,
            "urgent_alert_min_hits": 2,
        },
    }
    monkeypatch.setattr("liquidity.internal_checker.ocr_image_to_text", lambda path: "")

    snapshot = build_internal_checker_snapshot(config, now_iso="2026-03-09T12:00:00+00:00")

    assert snapshot["series"]["mom_5d"] == 1.08
    assert snapshot["series"]["mom_20d"] == -0.55
    assert snapshot["liquidity_direction"] == "EXPANDING"


def test_resolve_tesseract_cmd_prefers_env_and_falls_back_to_default(monkeypatch, tmp_path: Path):
    custom = tmp_path / "custom-tesseract.exe"
    custom.write_text("fake", encoding="utf-8")
    default_dir = tmp_path / "Tesseract-OCR"
    default_dir.mkdir()
    default = default_dir / "tesseract.exe"
    default.write_text("fake", encoding="utf-8")

    monkeypatch.setenv("TESSERACT_CMD", str(custom))
    assert _resolve_tesseract_cmd(default_path=default) == str(custom)

    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    assert _resolve_tesseract_cmd(default_path=default) == str(default)

    default.unlink()
    assert _resolve_tesseract_cmd(default_path=default) is None
