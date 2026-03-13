from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquidity.config import load_liquidity_config


def test_load_liquidity_config_reads_env_defaults(tmp_path: Path):
    config_path = tmp_path / "liquidity_checker.local.json"
    config_path.write_text(
        json.dumps(
            {
                "excel": {
                    "path_env": "LIQUIDITY_EXCEL_PATH",
                    "sheet_name": "Liquidity",
                    "date_column": "Date",
                    "metrics": {
                        "level": "LiquidityLevel",
                        "mom_5d": "LiquidityMom5D",
                        "mom_20d": "LiquidityMom20D",
                    },
                },
                "screenshot": {
                    "dir_env": "LIQUIDITY_SCREENSHOT_DIR",
                    "glob": "*.png",
                    "ocr_patterns": {"risk_off": "risk off"},
                },
                "thresholds": {
                    "mom_5d_positive": 0.5,
                    "mom_5d_negative": -0.5,
                    "mom_20d_positive": 1.5,
                    "mom_20d_negative": -1.5,
                    "urgent_alert_min_hits": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    excel_path = tmp_path / "daily.xlsx"
    screenshot_dir = tmp_path / "screens"
    screenshot_dir.mkdir()
    env = {
        "LIQUIDITY_CHECKER_CONFIG": str(config_path),
        "LIQUIDITY_EXCEL_PATH": str(excel_path),
        "LIQUIDITY_SCREENSHOT_DIR": str(screenshot_dir),
        "LIQUIDITY_OUTPUT_DIR": str(tmp_path / "outputs"),
        "LIQUIDITY_RAW_DIR": str(tmp_path / "raw"),
        "H_MODEL_AUTHOR_URL": "https://substack.com/@capitalwars",
        "H_MODEL_HEADLESS": "1",
        "H_MODEL_STALE_HOURS": "120",
    }

    cfg = load_liquidity_config(env)

    assert cfg["h_model"]["author_url"] == "https://substack.com/@capitalwars"
    assert cfg["h_model"]["headless"] is True
    assert cfg["h_model"]["stale_hours"] == 120
    assert cfg["checker"]["excel"]["path"] == excel_path
    assert cfg["checker"]["screenshot"]["dir"] == screenshot_dir
    assert cfg["paths"]["output_dir"] == tmp_path / "outputs"
    assert cfg["paths"]["raw_dir"] == tmp_path / "raw"


def test_load_liquidity_config_errors_when_local_config_missing(tmp_path: Path):
    env = {
        "LIQUIDITY_CHECKER_CONFIG": str(tmp_path / "missing.local.json"),
        "LIQUIDITY_OUTPUT_DIR": str(tmp_path / "outputs"),
        "LIQUIDITY_RAW_DIR": str(tmp_path / "raw"),
    }

    with pytest.raises(FileNotFoundError):
        load_liquidity_config(env)
