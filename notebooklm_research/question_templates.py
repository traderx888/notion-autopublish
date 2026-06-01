"""Fundamental research question templates for NotebookLM.

Routes to earnings-focused or sector-focused question sets
based on the signal source.
"""

from __future__ import annotations

from typing import Any


def build_earnings_questions(ticker: str, signal: dict | None = None) -> dict[str, str]:
    """Questions for EP-triggered individual stock research.

    Designed for earnings calls, investor presentations, and analyst coverage.
    """
    sig = signal or {}
    grade = sig.get("grade", "")
    gap_pct = sig.get("gap_pct", 0)

    grade_ctx = f" (Signal: {grade}, gap {gap_pct:.1f}%)" if grade else ""

    return {
        "earnings_delta": (
            f"For {ticker}{grade_ctx}, what changed in the most recent earnings? "
            "Summarise revenue beat/miss, guidance revision, and any margin surprise. "
            "Highlight the single biggest change versus the prior quarter."
        ),
        "management_tone": (
            f"Assess management's tone and confidence level for {ticker}. "
            "Are they sandbagging, genuinely optimistic, or hedging? "
            "Quote specific language if available."
        ),
        "risk_factors": (
            f"What are the key risks for {ticker} right now? "
            "Cover supply chain, competition, regulation, and macro headwinds. "
            "Rank them by likelihood and potential impact."
        ),
        "catalyst_timeline": (
            f"List near-term catalysts for {ticker}: product launches, "
            "regulatory approvals, partnerships, or next earnings date. "
            "Give approximate dates where possible."
        ),
        "competitive_position": (
            f"How does {ticker}'s competitive position compare to its closest peers? "
            "Evaluate moat strength, market share trajectory, and pricing power."
        ),
    }


def build_sector_questions(ticker: str, context: str = "") -> dict[str, str]:
    """Questions for SemiAnalysis/FOMO-triggered sector research.

    Focused on supply chain dynamics, capex cycles, and technology roadmaps.
    """
    ctx_note = f" Context: {context[:200]}" if context else ""

    return {
        "supply_chain_status": (
            f"What is the current supply chain status for {ticker}'s industry?{ctx_note} "
            "Cover bottlenecks, utilization rates, lead times, and any shortages. "
            "Distinguish between near-term constraints and structural issues."
        ),
        "capex_cycle": (
            f"Describe the capital expenditure trajectory for {ticker} and its peers. "
            "Are they in an investment upcycle or downcycle? "
            "What does this mean for capacity 12-18 months out?"
        ),
        "technology_roadmap": (
            f"Summarise the product and technology roadmap for {ticker}. "
            "What are the key product transitions, process node migrations, "
            "or platform shifts? Timeline and competitive positioning."
        ),
        "demand_signals": (
            f"What are the end-market demand signals for {ticker}'s products? "
            "Cover datacenter, consumer, auto, and industrial segments. "
            "Is the inventory cycle building or depleting?"
        ),
    }


def build_capscreen_questions(ticker: str, signal: dict | None = None) -> dict[str, str]:
    """Questions for DeepVue capscreen-triggered research.

    Lighter-weight: focused on technical setup validation + fundamental check.
    """
    sig = signal or {}
    stage = sig.get("stage", "")

    return {
        "fundamental_check": (
            f"For {ticker} (stage: {stage}), provide a quick fundamental health check. "
            "Revenue growth trend, profitability, debt load, and recent earnings surprise."
        ),
        "catalyst_or_risk": (
            f"What is the most likely near-term catalyst or risk for {ticker}? "
            "Is there an upcoming earnings date, FDA decision, product launch, "
            "or macro event that could move the stock?"
        ),
        "institutional_activity": (
            f"Any notable institutional activity for {ticker}? "
            "Recent 13F filings, insider buying/selling, analyst upgrades/downgrades."
        ),
    }


def select_question_set(target: dict[str, Any]) -> dict[str, str]:
    """Route to the appropriate question template based on signal source."""
    source = target.get("source", "")
    ticker = target.get("ticker", "")

    if source == "stockbee_ep":
        return build_earnings_questions(ticker, signal=target)
    elif source in ("semianalysis", "fomo"):
        context = target.get("context", "")
        return build_sector_questions(ticker, context=context)
    elif source == "deepvue_capscreen":
        return build_capscreen_questions(ticker, signal=target)
    elif source == "deepvue_stage":
        return build_sector_questions(ticker)
    else:
        # Default to earnings questions
        return build_earnings_questions(ticker, signal=target)
