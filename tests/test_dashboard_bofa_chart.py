from pathlib import Path


def test_dashboard_contains_bofa_chart_1_block() -> None:
    html = Path("output/dashboard.html").read_text(encoding="utf-8")

    assert 'class="bofa-chart"' in html
    assert "Chart 1: BofA Bull &amp; Bear Indicator" in html
    assert "Down to 8.4 from 8.5" in html
    assert "Source: BofA Global Investment Strategy" in html
