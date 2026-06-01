import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browser.scrapers.hedgefollow_insiders as hedgefollow_insiders


def _sample_manifest() -> dict:
    return {
        "generated_at": "2026-03-23T10:15:00+08:00",
        "source": "HedgeFollow",
        "window": "1W",
        "largest_buys_1w": [
            {
                "rank": 1,
                "symbol": "PHR",
                "company_name": "Phreesia Inc",
                "trade_value_text": "$18.3 M",
                "trade_value_numeric": 18_300_000.0,
                "range_low": "$10.75",
                "range_high": "$32.76",
                "primary_insider": "Pale Fire Capital Se",
                "insider_summary": "Pale Fire Capital Se - $18.3 M (1.6 M shares at $11.43)",
                "stock_url": "https://hedgefollow.com/stocks/PHR/insider-trading",
                "source_page": "https://hedgefollow.com/largest-insider-buys.php",
            }
        ],
        "largest_sells_1w": [
            {
                "rank": 1,
                "symbol": "RKLB",
                "company_name": "Rocket Lab USA Inc",
                "trade_value_text": "$30.6 M",
                "trade_value_numeric": 30_600_000.0,
                "range_low": "$3.47",
                "range_high": "$33.34",
                "primary_insider": "Khosla Ventures IV",
                "insider_summary": "Khosla Ventures IV - $30.6 M (1.1 M shares at $27.05)",
                "stock_url": "https://hedgefollow.com/stocks/RKLB/insider-trading",
                "source_page": "https://hedgefollow.com/largest-insider-sells.php",
            }
        ],
        "buy_page": "https://hedgefollow.com/largest-insider-buys.php",
        "sell_page": "https://hedgefollow.com/largest-insider-sells.php",
    }


def test_normalize_table_rows_filters_promos_and_extracts_primary_fields():
    raw_rows = [
        {
            "cells": [
                "PHR",
                "Phreesia Inc",
                "$ 18.3 M",
                "$10.75 $32.76",
                "Pale Fire Capital Se - $18.3 M (1.6 M shares at $11.43)",
            ],
            "stock_url": "https://hedgefollow.com/stocks/PHR/insider-trading",
        },
        {
            "cells": ["Remove Ads & Unlock Features for $10/Month"],
            "stock_url": "",
        },
        {
            "cells": [
                "GO",
                "Grocery Outlet Hldg Corp",
                "$ 2.9 M",
                "$5.66 $19.41",
                "Potter Jason J. N. - $1.7 M (286 k shares at $5.9) Ragatz Erik D. - $1.2 M (200 k shares at $5.95)",
            ],
            "stock_url": "https://hedgefollow.com/stocks/GO/insider-trading",
        },
    ]

    rows = hedgefollow_insiders.normalize_table_rows(
        raw_rows,
        source_page="https://hedgefollow.com/largest-insider-buys.php",
    )

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["symbol"] == "PHR"
    assert rows[0]["company_name"] == "Phreesia Inc"
    assert rows[0]["trade_value_text"] == "$18.3 M"
    assert rows[0]["trade_value_numeric"] == 18_300_000.0
    assert rows[0]["range_low"] == "$10.75"
    assert rows[0]["range_high"] == "$32.76"
    assert rows[0]["primary_insider"] == "Pale Fire Capital Se"
    assert rows[0]["stock_url"].endswith("/stocks/PHR/insider-trading")
    assert rows[1]["rank"] == 2
    assert rows[1]["primary_insider"] == "Potter Jason J. N."


def test_render_dashboard_section_outputs_buys_and_sells_tables():
    html = hedgefollow_insiders.render_dashboard_section(_sample_manifest(), row_limit=1)

    assert "Insider Flow" in html
    assert "Largest Insider Buys" in html
    assert "Largest Insider Sells" in html
    assert "PHR" in html
    assert "RKLB" in html
    assert "Pale Fire Capital Se" in html
    assert "Khosla Ventures IV" in html
    assert "https://hedgefollow.com/largest-insider-buys.php" in html
    assert "https://hedgefollow.com/largest-insider-sells.php" in html


def test_write_run_artifacts_emits_manifest_side_files_and_dashboard_snippet(tmp_path):
    manifest = hedgefollow_insiders.write_run_artifacts(_sample_manifest(), output_dir=tmp_path)

    latest_path = tmp_path / "hedgefollow_insiders_latest.json"
    buys_path = tmp_path / "largest_insider_buys.json"
    sells_path = tmp_path / "largest_insider_sells.json"
    section_path = tmp_path / "insider_dashboard_section.html"

    assert latest_path.exists()
    assert buys_path.exists()
    assert sells_path.exists()
    assert section_path.exists()

    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest_payload["generated_at"] == "2026-03-23T10:15:00+08:00"
    assert latest_payload["largest_buys_1w"][0]["symbol"] == "PHR"
    assert json.loads(buys_path.read_text(encoding="utf-8"))[0]["symbol"] == "PHR"
    assert json.loads(sells_path.read_text(encoding="utf-8"))[0]["symbol"] == "RKLB"
    assert "Insider Flow" in section_path.read_text(encoding="utf-8")
    assert manifest["largest_sells_1w"][0]["primary_insider"] == "Khosla Ventures IV"
