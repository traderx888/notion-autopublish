from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_review_backtest_dashboard import build_dashboard


def test_build_dashboard_summarizes_backtest_csv_and_review_reports(tmp_path: Path):
    outputs = tmp_path / "outputs"
    review = tmp_path / "review"
    dashboard_path = tmp_path / "output" / "review_backtest_dashboard.html"
    snapshot_path = outputs / "backtest" / "review_backtest_dashboard_latest.json"
    outputs.mkdir()
    review.mkdir()
    (outputs / "backtest_2026Q1.csv").write_text(
        "\n".join(
            [
                "page_id,title,publish_date,direction,tickers,strategy_return_pct,benchmark_return_pct,alpha_pct,status",
                "p1,Micron upside,2026-01-01,Long,MU,15.0,5.0,10.0,Hit",
                "p2,SK Hynix pair,2026-01-02,Pair Trade,000660.KS,4.0,0.0,4.0,Partial Hit",
                "p3,Weak setup,2026-01-03,Long,SPY,-2.0,2.0,-4.0,Miss",
            ]
        ),
        encoding="utf-8",
    )
    (review / "review_2026-05-26.md").write_text(
        "# 30-Day Review Report\n\n## Section 1\n- Micron upside\n",
        encoding="utf-8",
    )

    snapshot = build_dashboard(outputs_dir=outputs, review_dir=review, dashboard_path=dashboard_path)

    html = dashboard_path.read_text(encoding="utf-8")
    assert snapshot["backtests"]["totalRows"] == 3
    assert snapshot["backtests"]["statusCounts"]["Hit"] == 1
    assert snapshot["backtests"]["statusCounts"]["Partial Hit"] == 1
    assert snapshot["backtests"]["statusCounts"]["Miss"] == 1
    assert snapshot["backtests"]["gradedHitRatePct"] == 50.0
    assert snapshot_path.exists()
    assert "Review / Backtest Monitor" in html
    assert "backtest_2026Q1.csv" in html
    assert "review_2026-05-26.md" in html
    assert "Micron upside" in html
    assert "Avg Alpha" in html


def test_build_dashboard_renders_empty_state_without_fabricated_results(tmp_path: Path):
    outputs = tmp_path / "outputs"
    review = tmp_path / "review"
    dashboard_path = tmp_path / "output" / "review_backtest_dashboard.html"
    outputs.mkdir()
    review.mkdir()

    snapshot = build_dashboard(outputs_dir=outputs, review_dir=review, dashboard_path=dashboard_path)

    html = dashboard_path.read_text(encoding="utf-8")
    assert snapshot["backtests"]["totalRows"] == 0
    assert "No backtest CSVs found" in html
    assert "No review reports found" in html
    assert "python backtest/run_backtest.py --quarter 2026Q1" in html
