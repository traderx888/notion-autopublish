from __future__ import annotations

from datetime import datetime
from importlib import import_module
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_quarter_to_range_supports_calendar_quarters():
    mod = import_module("backtest.run_backtest")

    start, end = mod.quarter_to_range("2026Q1")

    assert start == "2026-01-01"
    assert end == "2026-03-31"


def test_extract_tickers_resolves_aliases_and_explicit_symbols():
    mod = import_module("backtest.run_backtest")
    thesis = mod.ThesisEntry(
        page_id="page-1",
        title="Memory leaders",
        publish_date=datetime(2026, 1, 15),
        direction="Long",
        time_horizon="3-6 months",
        asset_class=["Korean Equity"],
        tags=["Memory"],
        verdict="Long SK Hynix and $MU, monitor 1810.HK.",
        series="Newsletter",
    )

    assert thesis.extract_tickers() == ["000660.KS", "MU", "1810.HK"]


def test_evaluate_long_thesis_uses_injected_prices_and_benchmark_alpha():
    mod = import_module("backtest.run_backtest")

    prices = {
        "MU": [100.0, 115.0],
        "SPY": [100.0, 105.0],
    }

    def fake_price_provider(ticker, start_date, end_date):
        return pd.DataFrame({"Close": prices[ticker]})

    thesis = mod.ThesisEntry(
        page_id="page-2",
        title="Micron upside",
        publish_date=datetime(2026, 1, 1),
        direction="Long",
        time_horizon="1-3 months",
        asset_class=["US Equity"],
        tags=["Semiconductors"],
        verdict="Long $MU as HBM demand improves.",
        series="Newsletter",
    )
    engine = mod.BacktestEngine(benchmark="SPY", price_provider=fake_price_provider)

    result = engine.evaluate_thesis(thesis, datetime(2026, 1, 31))

    assert result["status"] == "Hit"
    assert result["strategy_return_pct"] == 15.0
    assert result["benchmark_return_pct"] == 5.0
    assert result["alpha_pct"] == 10.0


def test_short_thesis_skips_for_forbidden_asset_class():
    mod = import_module("backtest.run_backtest")
    thesis = mod.ThesisEntry(
        page_id="page-3",
        title="Forbidden short",
        publish_date=datetime(2026, 1, 1),
        direction="Short",
        time_horizon="1-3 months",
        asset_class=["A-Share"],
        tags=[],
        verdict="Short $ASHR.",
        series="Newsletter",
    )
    engine = mod.BacktestEngine(benchmark="SPY", price_provider=lambda *_: pd.DataFrame())

    result = engine.evaluate_thesis(thesis, datetime(2026, 1, 31))

    assert result["status"] == "skip"
    assert result["reason"] == "Cannot short A-Share (operator rule)"


def test_short_rule_does_not_match_em_inside_other_words():
    mod = import_module("backtest.run_backtest")
    thesis = mod.ThesisEntry(
        page_id="page-3b",
        title="Semiconductor short",
        publish_date=datetime(2026, 1, 1),
        direction="Short",
        time_horizon="1-3 months",
        asset_class=["US Equity"],
        tags=["Semiconductors"],
        verdict="Short $MU.",
        series="Newsletter",
    )

    assert thesis.check_short_rules() == (True, "OK")


def test_write_back_to_notion_uses_review_properties():
    mod = import_module("backtest.run_backtest")

    class FakePages:
        def __init__(self):
            self.calls = []

        def update(self, **kwargs):
            self.calls.append(kwargs)

    class FakeNotion:
        def __init__(self):
            self.pages = FakePages()

    notion = FakeNotion()
    engine = mod.BacktestEngine(benchmark="SPY", notion_client=notion)
    result = {
        "page_id": "page-4",
        "title": "Micron upside",
        "publish_date": "2026-01-01",
        "direction": "Long",
        "tickers": ["MU"],
        "returns_pct": {"MU": 15.0},
        "strategy_return_pct": 15.0,
        "benchmark_return_pct": 5.0,
        "alpha_pct": 10.0,
        "status": "Hit",
    }

    engine.write_back_to_notion(result, datetime(2026, 1, 31))

    call = notion.pages.calls[0]
    assert call["page_id"] == "page-4"
    assert call["properties"]["Hit/Miss Status"]["select"]["name"] == "Hit"
    assert call["properties"]["Verification Date"]["date"]["start"] == "2026-01-31"
    assert "Alpha=10.0%" in call["properties"]["Key Trigger"]["rich_text"][0]["text"]["content"]
