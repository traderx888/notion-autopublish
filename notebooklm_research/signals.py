"""Extract research targets from quant signal sources.

Reads structured signal files (SMM Golden EP, SemiAnalysis, FOMO, DeepVue)
and produces a prioritised list of tickers/sectors for NotebookLM research.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ── Company → ticker mapping for article text extraction ──────

COMPANY_TICKER_MAP: dict[str, str] = {
    "nvidia": "NVDA",
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "tsmc": "TSM",
    "taiwan semiconductor": "TSM",
    "intel": "INTC",
    "qualcomm": "QCOM",
    "broadcom": "AVGO",
    "samsung": "005930.KS",
    "sk hynix": "000660.KS",
    "micron": "MU",
    "apple": "AAPL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "microsoft": "MSFT",
    "mediatek": "2454.TW",
    "arm holdings": "ARM",
    "arm ": "ARM",
    "asml": "ASML",
    "applied materials": "AMAT",
    "lam research": "LRCX",
    "marvell": "MRVL",
    "tesla": "TSLA",
}

# Stage-2A heavy → likely sector ETF rotation targets
SECTOR_ETF_MAP: dict[str, str] = {
    "technology": "XLK",
    "financials": "XLF",
    "healthcare": "XLV",
    "energy": "XLE",
    "industrials": "XLI",
    "consumer_discretionary": "XLY",
    "consumer_staples": "XLP",
    "materials": "XLB",
    "utilities": "XLU",
    "real_estate": "XLRE",
    "communication": "XLC",
}

# Grade priority for sorting (lower = higher priority)
_GRADE_PRIORITY = {
    "SUPER_SWAN": 0,
    "SWAN": 1,
    "DUCK": 2,
    "CHICKEN": 3,
}


def extract_ep_tickers(
    momentum_path: Path,
    *,
    min_grade: str = "SWAN",
    golden_only: bool = False,
) -> list[dict[str, Any]]:
    """Extract tickers from SMM episodic pivot signals.

    Reads ``stockbee_momentum.json`` and filters ``episodic_pivots.top_eps[]``
    by grade threshold and optional golden flag.
    """
    if not momentum_path.exists():
        return []

    data = json.loads(momentum_path.read_text(encoding="utf-8"))
    eps = data.get("episodic_pivots", {}).get("top_eps", [])
    min_priority = _GRADE_PRIORITY.get(min_grade, 1)

    targets = []
    for ep in eps:
        grade = ep.get("grade", "")
        grade_priority = _GRADE_PRIORITY.get(grade, 99)
        if grade_priority > min_priority:
            continue
        if golden_only and not ep.get("is_golden", False):
            continue
        targets.append({
            "ticker": ep["ticker"],
            "source": "stockbee_ep",
            "grade": grade,
            "is_golden": ep.get("is_golden", False),
            "gap_pct": ep.get("gap_pct", 0),
            "vol_multiple": ep.get("vol_multiple", 0),
            "price": ep.get("price", 0),
            "date": ep.get("date", ""),
        })

    return targets


def extract_semi_tickers(text_path: Path) -> list[dict[str, Any]]:
    """Extract company/ticker mentions from SemiAnalysis article text."""
    if not text_path.exists():
        return []

    text = text_path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []

    lowered = text.lower()
    seen: set[str] = set()
    targets = []

    for company, ticker in COMPANY_TICKER_MAP.items():
        if ticker in seen:
            continue
        # Find mention position for context extraction
        idx = lowered.find(company.lower())
        if idx == -1:
            continue
        seen.add(ticker)
        # Extract ~200 chars of context around the mention
        start = max(0, idx - 50)
        end = min(len(text), idx + 150)
        context = text[start:end].strip()
        targets.append({
            "ticker": ticker,
            "source": "semianalysis",
            "context": context,
        })

    return targets


def extract_fomo_tickers(text_path: Path) -> list[dict[str, Any]]:
    """Extract company/ticker mentions from FOMO article text."""
    if not text_path.exists():
        return []

    text = text_path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []

    lowered = text.lower()
    seen: set[str] = set()
    targets = []

    for company, ticker in COMPANY_TICKER_MAP.items():
        if ticker in seen:
            continue
        idx = lowered.find(company.lower())
        if idx == -1:
            continue
        seen.add(ticker)
        start = max(0, idx - 50)
        end = min(len(text), idx + 150)
        context = text[start:end].strip()
        targets.append({
            "ticker": ticker,
            "source": "fomo",
            "context": context,
        })

    return targets


def extract_deepvue_sectors(overview_path: Path) -> list[dict[str, Any]]:
    """Extract sector-level targets from DeepVue stage analysis.

    When stage_2a percentage is elevated (>= 30%), flag the broad market
    as having momentum. Returns sector ETF targets.
    """
    if not overview_path.exists():
        return []

    data = json.loads(overview_path.read_text(encoding="utf-8"))
    stages = data.get("stages", {})
    stage_2 = stages.get("stage_2", {})
    stage_2_pct = stage_2.get("pct", 0) if isinstance(stage_2, dict) else 0

    targets = []
    if stage_2_pct >= 30:
        targets.append({
            "ticker": "XLK",
            "source": "deepvue_stage",
            "note": f"stage_2 pct={stage_2_pct}%, broad momentum elevated",
        })

    return targets


def extract_deepvue_capscreen(capscreen_path: Path) -> list[dict[str, Any]]:
    """Extract individual tickers from DeepVue capscreen output."""
    if not capscreen_path.exists():
        return []

    data = json.loads(capscreen_path.read_text(encoding="utf-8"))
    tickers_list = data.get("tickers", [])

    targets = []
    for entry in tickers_list:
        ticker = entry.get("ticker", "").strip()
        if not ticker:
            continue
        targets.append({
            "ticker": ticker,
            "source": "deepvue_capscreen",
            "stage": entry.get("stage", ""),
            "gap_pct": entry.get("gap_pct", 0),
        })

    return targets


def collect_research_targets(
    *,
    scraped_dir: Path | None = None,
    fundman_data_dir: Path | None = None,
    max_targets: int = 10,
) -> list[dict[str, Any]]:
    """Aggregate targets from all signal sources, dedup and prioritise.

    Priority order: SUPER_SWAN > SWAN > deepvue_capscreen > article mentions
    """
    scraped = scraped_dir or Path("scraped_data")
    targets: list[dict[str, Any]] = []

    # SMM Golden EP / SuperSwan
    if fundman_data_dir:
        momentum_path = fundman_data_dir / "stockbee_momentum.json"
        targets.extend(extract_ep_tickers(momentum_path))

    # SemiAnalysis
    semi_path = scraped / "substack_authors" / "semianalysis_latest.txt"
    targets.extend(extract_semi_tickers(semi_path))

    # FOMO
    fomo_path = scraped / "substack_authors" / "fomosoc_latest.txt"
    targets.extend(extract_fomo_tickers(fomo_path))

    # DeepVue stage analysis
    deepvue_overview = scraped / "deepvue" / "market_overview.json"
    targets.extend(extract_deepvue_sectors(deepvue_overview))

    # DeepVue capscreen
    deepvue_capscreen = scraped / "deepvue" / "capscreen.json"
    targets.extend(extract_deepvue_capscreen(deepvue_capscreen))

    # Dedup by ticker (keep highest priority)
    seen: dict[str, dict] = {}
    for t in targets:
        ticker = t["ticker"]
        if ticker not in seen:
            seen[ticker] = t
        else:
            # Keep the one with higher priority source
            existing = seen[ticker]
            if _target_priority(t) < _target_priority(existing):
                seen[ticker] = t

    deduped = list(seen.values())
    deduped.sort(key=_target_priority)
    return deduped[:max_targets]


def _target_priority(target: dict) -> int:
    """Lower = higher priority."""
    source = target.get("source", "")
    if source == "stockbee_ep":
        grade = target.get("grade", "")
        base = _GRADE_PRIORITY.get(grade, 3)
        if target.get("is_golden"):
            return base  # golden gets full grade priority
        return base + 5  # non-golden demoted
    if source == "deepvue_capscreen":
        return 10
    if source in ("semianalysis", "fomo"):
        return 20
    if source == "deepvue_stage":
        return 30
    return 50
