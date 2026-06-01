import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dashboard_freshness_module():
    module_path = REPO_ROOT / "tools" / "dashboard_freshness.py"
    spec = importlib.util.spec_from_file_location("dashboard_freshness", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SMM_SAMPLE_CSV = """,Primary Breadth Indicators,,,,,,Secondary Breadth Indicators,,,,,,,,
Date,Number of stocks up 4% plus today,Number of stocks down 4% plus today,5 day ratio,10 day  ratio ,Number of stocks up 25% plus in a quarter,Number of stocks down 25% + in a quarter,Number of stocks up 25% + in a month,Number of stocks down 25% + in a month,Number of stocks up 50% + in a month,Number of stocks down 50% + in a month,Number of stocks up 13% + in 34 days,Number of stocks down 13% + in 34 days, Worden Common stock universe,T2108 ,S&P
3/24/2026,223,285,0.50,0.63,951,1474,105,195,28,28,1110,2236,6402,22.97,"6,556.37"
3/23/2026,235,85,0.58,0.66,947,1420,124,163,26,21,1111,2212,6404,20.99,"6,581.00"
3/20/2026,146,662,0.60,0.68,829,1572,88,260,22,29,950,2505,6395,16.74,"6,506.48"
"""

AASTOCKS_HIGH_HTML = """
<html>
  <head><meta name="aa-update" content="2026-03-25 16:08:00" /></head>
  <body>
    <table id="tblTS2" class="HIGHLOWSTOCKS">
      <tbody>
        <tr><td><a href="/en/stocks/quote/detail-quote.aspx?symbol=00107" title="00107.HK">00107.HK</a></td></tr>
        <tr><td><a href="/en/stocks/quote/detail-quote.aspx?symbol=00548" title="00548.HK">00548.HK</a></td></tr>
      </tbody>
    </table>
    <div class="tabPanel_RemarksLastUpdate">(#) Information is delayed for at least 15 minutes. Last Update: 2026/03/25 16:08</div>
  </body>
</html>
"""

AASTOCKS_LOW_HTML = """
<html>
  <head><meta name="aa-update" content="2026-03-25 16:08:00" /></head>
  <body>
    <table id="tblTS2" class="HIGHLOWSTOCKS">
      <tbody>
        <tr><td><a href="/en/stocks/quote/detail-quote.aspx?symbol=00005" title="00005.HK">00005.HK</a></td></tr>
        <tr><td><a href="/en/stocks/quote/detail-quote.aspx?symbol=00700" title="00700.HK">00700.HK</a></td></tr>
        <tr><td><a href="/en/stocks/quote/detail-quote.aspx?symbol=09988" title="09988.HK">09988.HK</a></td></tr>
      </tbody>
    </table>
    <div class="tabPanel_RemarksLastUpdate">(#) Information is delayed for at least 15 minutes. Last Update: 2026/03/25 16:08</div>
  </body>
</html>
"""


def _sample_snapshot() -> dict:
    return {
        "generatedAt": "2026-03-25T16:20:00+08:00",
        "sources": {
            "smm": {
                "capturedAt": "2026-03-25T09:10:00+08:00",
                "marketDate": "2026-03-24",
                "status": "fresh",
                "score": 57.8,
                "signalLabel": "OVERSOLD REBOUND WATCH",
                "signalTone": "neutral",
                "metrics": {
                    "universeCount": 6402,
                    "up4Count": 223,
                    "up4Pct": 3.5,
                    "down4Count": 285,
                    "down4Pct": 4.5,
                    "ratio5d": 0.50,
                    "ratio10d": 0.63,
                    "qtrUp25Count": 951,
                    "qtrUp25Pct": 14.9,
                    "qtrDown25Count": 1474,
                    "qtrDown25Pct": 23.0,
                    "monthUp25Count": 105,
                    "monthUp25Pct": 1.6,
                    "monthDown25Count": 195,
                    "monthDown25Pct": 3.0,
                    "monthUp50Count": 28,
                    "monthDown50Count": 28,
                    "up13In34dCount": 1110,
                    "up13In34dPct": 17.3,
                    "down13In34dCount": 2236,
                    "down13In34dPct": 34.9,
                    "ma40Pct": 22.97,
                    "spxClose": 6556.37,
                    "spxChange1dPct": -0.38,
                    "spxChange5dPct": 0.77,
                },
                "thesis": "Public SMM sheet shows improving breadth versus March 20 but the market remains below ideal participation thresholds.",
            },
            "deepvue": {
                "capturedAt": "2026-03-25T15:35:00+08:00",
                "marketDate": "2026-03-25",
                "status": "fresh",
                "score": 31.0,
                "signalLabel": "BROAD DOWNTREND",
                "signalTone": "bearish",
                "metrics": {
                    "advanceCount": 466,
                    "declineCount": 1874,
                    "advanceDeclinePct": 20,
                    "highsCount": 76,
                    "lowsCount": 131,
                    "newHighsVsLowsPct": 37,
                    "upFromOpenPct": 33,
                    "upVolumePct": 13,
                    "up4Pct": 17,
                    "stage1Count": 51,
                    "stage1Pct": 1,
                    "stage2Count": 1381,
                    "stage2Pct": 25,
                    "stage3Count": 1048,
                    "stage3Pct": 19,
                    "stage4Count": 3096,
                    "stage4Pct": 56,
                },
                "thesis": "Stage 4 still dominates and volume participation is weak.",
            },
            "hkBreadth": {
                "capturedAt": "2026-03-25T16:20:00+08:00",
                "marketDate": "2026-03-25",
                "status": "error",
                "score": None,
                "signalLabel": "PARTIAL DATA",
                "signalTone": "caution",
                "metrics": {
                    "sourceName": "AASTOCKS",
                    "liquidStockCount": None,
                    "pctAbove20Ma": None,
                    "pctAbove50Ma": None,
                    "pctAbove200Ma": None,
                    "advancePct": None,
                    "declinePct": None,
                    "advanceDeclineRatio": None,
                    "newHighs52w": 2,
                    "newLows52w": 3,
                    "highLowRatio": 0.67,
                    "up20In63dPct": None,
                    "strongUpPct": None,
                    "strongDownPct": None,
                },
                "thesis": "AASTOCKS highs/lows refreshed, but moving-average breadth is unavailable in the current scraper.",
                "lastError": "AASTOCKS moving-average breadth page not yet wired",
            },
        },
    }


def _extract_between_markers(html: str, start_marker: str, end_marker: str) -> str:
    start = html.index(start_marker)
    end = html.index(end_marker, start)
    return html[start:end]


def test_parse_smm_csv_extracts_latest_row_and_metrics():
    module = _load_dashboard_freshness_module()

    payload = module.parse_smm_csv(
        SMM_SAMPLE_CSV,
        captured_at="2026-03-25T09:10:00+08:00",
    )

    assert payload["marketDate"] == "2026-03-24"
    assert payload["capturedAt"] == "2026-03-25T09:10:00+08:00"
    assert payload["metrics"]["up4Count"] == 223
    assert payload["metrics"]["down4Count"] == 285
    assert payload["metrics"]["universeCount"] == 6402
    assert payload["metrics"]["ma40Pct"] == 22.97
    assert payload["metrics"]["spxClose"] == 6556.37
    assert payload["signalLabel"]
    assert payload["thesis"]


def test_normalize_deepvue_payload_maps_existing_market_overview_fields():
    module = _load_dashboard_freshness_module()

    payload = module.normalize_deepvue_payload(
        {
            "timestamp": "2026-03-25T15:35:00+08:00",
            "breadth": {
                "advance_count": 466,
                "decline_count": 1874,
                "advance_decline_pct": 20,
                "highs_count": 76,
                "lows_count": 131,
                "new_highs_vs_lows_pct": 37,
                "up_from_open_pct": 33,
                "up_volume_pct": 13,
                "up_4pct_pct": 17,
            },
            "stages": {
                "stage_1": {"count": 51, "pct": 1},
                "stage_2": {"count": 1381, "pct": 25},
                "stage_3": {"count": 1048, "pct": 19},
                "stage_4": {"count": 3096, "pct": 56},
            },
        }
    )

    assert payload["marketDate"] == "2026-03-25"
    assert payload["metrics"]["advanceCount"] == 466
    assert payload["metrics"]["stage4Pct"] == 56
    assert payload["signalTone"] == "bearish"
    assert "Stage 4" in payload["thesis"]


def test_parse_aastocks_high_low_pages_extracts_counts_and_missing_fields():
    module = _load_dashboard_freshness_module()

    payload = module.parse_aastocks_high_low_pages(
        AASTOCKS_HIGH_HTML,
        AASTOCKS_LOW_HTML,
        captured_at="2026-03-25T16:20:00+08:00",
    )

    assert payload["marketDate"] == "2026-03-25"
    assert payload["metrics"]["newHighs52w"] == 2
    assert payload["metrics"]["newLows52w"] == 3
    assert payload["metrics"]["highLowRatio"] == 0.67
    assert payload["metrics"]["pctAbove20Ma"] is None
    assert payload["signalLabel"] == "PARTIAL DATA"


def test_evaluate_source_status_distinguishes_fresh_stale_and_error():
    module = _load_dashboard_freshness_module()

    fresh = module.evaluate_source_status(
        market_date="2026-03-25",
        last_attempt_ok=True,
        now_iso="2026-03-25T17:00:00+08:00",
    )
    stale = module.evaluate_source_status(
        market_date="2026-03-20",
        last_attempt_ok=True,
        now_iso="2026-03-25T17:00:00+08:00",
    )
    error = module.evaluate_source_status(
        market_date="2026-03-25",
        last_attempt_ok=False,
        now_iso="2026-03-25T17:00:00+08:00",
    )

    yesterday_stale = module.evaluate_source_status(
        market_date="2026-03-24",
        last_attempt_ok=True,
        now_iso="2026-03-25T09:00:00+08:00",
    )

    assert fresh == "fresh"
    assert stale == "stale"
    assert error == "error"
    # Strict same-HKT-day rule: yesterday's capture must not be considered fresh,
    # so Telegram/CIO consumers never read across-day artifacts.
    assert yesterday_stale == "stale"


def test_render_dashboard_html_rebuilds_breadth_block_and_freshness_copy():
    module = _load_dashboard_freshness_module()
    template_html = (REPO_ROOT / "output" / "dashboard.html").read_text(encoding="utf-8")

    rendered = module.render_dashboard_html(template_html, _sample_snapshot())

    breadth_block = _extract_between_markers(
        rendered,
        "<!-- MARKET BREADTH -->",
        "<!-- MACRO & LIQUIDITY -->",
    )

    assert "Market Breadth auto-refresh" in rendered
    assert "Mar 25, 2026" in rendered
    assert "FRESH" in breadth_block
    assert "ERROR" in breadth_block
    assert "Mar 11, 2026" not in breadth_block
    assert "Mar 13" not in breadth_block
    assert "Mar 20, 2026" not in breadth_block
    assert "AASTOCKS moving-average breadth page not yet wired" in breadth_block


def test_dashboard_refresh_workflow_targets_self_hosted_schedule():
    workflow_path = REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml"
    text = workflow_path.read_text(encoding="utf-8")

    assert "self-hosted" in text
    assert "windows" in text
    assert "workflow_dispatch" in text
    assert "10 1 * * 1-5" in text
    assert "35 7 * * 1-5" in text
    assert "20 8 * * 1-5" in text
