"""Tests for notebooklm_research.signals — signal extraction from all sources."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notebooklm_research.signals import (
    collect_research_targets,
    extract_deepvue_capscreen,
    extract_deepvue_sectors,
    extract_ep_tickers,
    extract_fomo_tickers,
    extract_semi_tickers,
)


# ── Fixtures ──────────────────────────────────────────────────


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


SAMPLE_MOMENTUM = {
    "episodic_pivots": {
        "count": 310,
        "golden_count": 2,
        "grade_distribution": {"SUPER_SWAN": 1, "SWAN": 2, "DUCK": 100, "CHICKEN": 207},
        "top_eps": [
            {
                "ticker": "XENE",
                "date": "2026-03-09",
                "gap_pct": 43.37,
                "vol_multiple": 12.82,
                "price": 62.76,
                "grade": "SUPER_SWAN",
                "is_golden": True,
                "close": 62.76,
            },
            {
                "ticker": "DNTH",
                "date": "2026-03-10",
                "gap_pct": 18.5,
                "vol_multiple": 6.63,
                "price": 79.23,
                "grade": "SWAN",
                "is_golden": True,
                "close": 79.23,
            },
            {
                "ticker": "LOWQ",
                "date": "2026-03-10",
                "gap_pct": 3.2,
                "vol_multiple": 2.1,
                "price": 15.0,
                "grade": "DUCK",
                "is_golden": False,
                "close": 15.0,
            },
        ],
    }
}

SAMPLE_SEMI_TEXT = (
    "The Great AI Silicon Shortage\n"
    "TSMC N3 Wafer Shortages, Memory Constraints\n"
    "NVIDIA transitions from 4NP with Blackwell to 3NP with Rubin.\n"
    "AMD has already adopted N3 for MI350X.\n"
    "Google's TPU roadmap shifts fully to N3E.\n"
    "Intel for its Lunar Lake and Arrow Lake client processors.\n"
    "Broadcom is also ramping custom silicon.\n"
)


# ── Tests ─────────────────────────────────────────────────────


def test_extract_ep_tickers_filters_by_grade(tmp_path: Path):
    path = _write_json(tmp_path / "stockbee_momentum.json", SAMPLE_MOMENTUM)
    targets = extract_ep_tickers(path, min_grade="SWAN")

    tickers = [t["ticker"] for t in targets]
    assert "XENE" in tickers
    assert "DNTH" in tickers
    assert "LOWQ" not in tickers  # DUCK excluded


def test_extract_ep_tickers_golden_only(tmp_path: Path):
    path = _write_json(tmp_path / "stockbee_momentum.json", SAMPLE_MOMENTUM)
    targets = extract_ep_tickers(path, min_grade="SWAN", golden_only=True)

    assert all(t["is_golden"] for t in targets)
    assert len(targets) == 2  # XENE + DNTH


def test_extract_ep_tickers_preserves_signal_data(tmp_path: Path):
    path = _write_json(tmp_path / "stockbee_momentum.json", SAMPLE_MOMENTUM)
    targets = extract_ep_tickers(path)

    xene = next(t for t in targets if t["ticker"] == "XENE")
    assert xene["source"] == "stockbee_ep"
    assert xene["grade"] == "SUPER_SWAN"
    assert xene["gap_pct"] == 43.37
    assert xene["is_golden"] is True


def test_extract_ep_tickers_missing_file(tmp_path: Path):
    assert extract_ep_tickers(tmp_path / "nonexistent.json") == []


def test_extract_semi_tickers(tmp_path: Path):
    path = _write_text(tmp_path / "semi.txt", SAMPLE_SEMI_TEXT)
    targets = extract_semi_tickers(path)

    tickers = {t["ticker"] for t in targets}
    assert "NVDA" in tickers
    assert "AMD" in tickers
    assert "TSM" in tickers
    assert "INTC" in tickers
    assert "AVGO" in tickers
    assert all(t["source"] == "semianalysis" for t in targets)


def test_extract_semi_tickers_has_context(tmp_path: Path):
    path = _write_text(tmp_path / "semi.txt", SAMPLE_SEMI_TEXT)
    targets = extract_semi_tickers(path)

    nvda = next(t for t in targets if t["ticker"] == "NVDA")
    assert "context" in nvda
    assert len(nvda["context"]) > 0


def test_extract_semi_tickers_empty_file(tmp_path: Path):
    path = _write_text(tmp_path / "semi.txt", "")
    assert extract_semi_tickers(path) == []


def test_extract_fomo_tickers(tmp_path: Path):
    path = _write_text(tmp_path / "fomo.txt", "Apple is launching a new AI chip. Tesla reported strong deliveries.")
    targets = extract_fomo_tickers(path)

    tickers = {t["ticker"] for t in targets}
    assert "AAPL" in tickers
    assert "TSLA" in tickers
    assert all(t["source"] == "fomo" for t in targets)


def test_extract_deepvue_sectors_high_stage2(tmp_path: Path):
    data = {"stages": {"stage_2": {"count": 1500, "pct": 35}}}
    path = _write_json(tmp_path / "market_overview.json", data)
    targets = extract_deepvue_sectors(path)

    assert len(targets) == 1
    assert targets[0]["ticker"] == "XLK"
    assert targets[0]["source"] == "deepvue_stage"


def test_extract_deepvue_sectors_low_stage2(tmp_path: Path):
    data = {"stages": {"stage_2": {"count": 500, "pct": 15}}}
    path = _write_json(tmp_path / "market_overview.json", data)
    targets = extract_deepvue_sectors(path)

    assert targets == []


def test_extract_deepvue_capscreen(tmp_path: Path):
    data = {
        "tickers": [
            {"ticker": "SMCI", "stage": "2A", "gap_pct": 8.5},
            {"ticker": "PLTR", "stage": "2", "gap_pct": 3.1},
        ]
    }
    path = _write_json(tmp_path / "capscreen.json", data)
    targets = extract_deepvue_capscreen(path)

    assert len(targets) == 2
    assert targets[0]["ticker"] == "SMCI"
    assert targets[0]["source"] == "deepvue_capscreen"
    assert targets[1]["ticker"] == "PLTR"


def test_collect_research_targets_dedup_and_priority(tmp_path: Path):
    # Setup: NVDA appears in both EP and SemiAnalysis
    momentum = {
        "episodic_pivots": {
            "top_eps": [
                {
                    "ticker": "NVDA",
                    "date": "2026-03-09",
                    "gap_pct": 10.0,
                    "vol_multiple": 5.5,
                    "price": 800.0,
                    "grade": "SUPER_SWAN",
                    "is_golden": True,
                    "close": 800.0,
                },
            ]
        }
    }
    fundman_dir = tmp_path / "fundman"
    fundman_dir.mkdir()
    _write_json(fundman_dir / "stockbee_momentum.json", momentum)

    scraped_dir = tmp_path / "scraped"
    _write_text(
        scraped_dir / "substack_authors" / "semianalysis_latest.txt",
        "NVIDIA is seeing huge demand for Blackwell.",
    )
    # Empty FOMO
    _write_text(scraped_dir / "substack_authors" / "fomosoc_latest.txt", "")

    targets = collect_research_targets(
        scraped_dir=scraped_dir,
        fundman_data_dir=fundman_dir,
        max_targets=10,
    )

    # NVDA should appear once, with stockbee_ep source (higher priority)
    nvda_targets = [t for t in targets if t["ticker"] == "NVDA"]
    assert len(nvda_targets) == 1
    assert nvda_targets[0]["source"] == "stockbee_ep"

    # All targets should be sorted by priority
    for i in range(len(targets) - 1):
        assert targets[i].get("grade", "") or targets[i].get("source", "") != ""
