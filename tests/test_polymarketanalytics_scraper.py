import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browser.scrapers.polymarketanalytics as polymarketanalytics


def test_normalize_leaderboard_rows_extracts_public_fields_and_fallback_handle():
    raw_rows = [
        {
            "trader": "0x1111222233334444555566667777888899990000",
            "trader_name": "Theo4",
            "overall_gain": 22053933.752321757,
            "active_positions": 8,
            "win_amount": 22053952.727256756,
            "loss_amount": -18.974934999999988,
            "win_rate": 0.8888888888888888,
            "total_current_value": 125000.5,
            "total_positions": 22,
            "rank": 1,
            "trader_tags": "Overall PnL > $1m",
        },
        {
            "trader": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "trader_name": "",
            "overall_gain": 1800000,
            "active_positions": 6,
            "win_amount": 2500000,
            "loss_amount": -700000,
            "win_rate": 0.61,
            "total_current_value": 90000,
            "total_positions": 50,
            "rank": 2,
            "trader_tags": "",
        },
    ]

    rows = polymarketanalytics.normalize_leaderboard_rows(raw_rows)

    assert rows[0]["rank"] == 1
    assert rows[0]["wallet"] == "0x1111222233334444555566667777888899990000"
    assert rows[0]["handle"] == "Theo4"
    assert rows[0]["display_name"] == "Theo4"
    assert rows[0]["total_pnl"] == 22053933.75
    assert rows[0]["win_rate_pct"] == 88.9
    assert rows[0]["active_positions"] == 8
    assert rows[0]["current_value"] == 125000.5
    assert rows[1]["handle"] == ""
    assert rows[1]["display_name"].startswith("0xabcd")


def test_normalize_activity_rows_extracts_trade_fields():
    raw_rows = [
        {
            "trade_dttm": "2026-03-26 08:49:29",
            "trader_id": "0x94f199fb7789f1aef7fff6b758d6b375100f4c7a",
            "trader_name": "KeyTransporter",
            "side": "buy",
            "amount": 430158.73,
            "price": 0.63,
            "value": 271000.0,
            "event_id": "98765",
            "market_title": "Will the next Prime Minister of Hungary be Péter Magyar?",
            "market_subtitle": "",
            "outcome": "Yes",
            "trader_tags": "Overall Win Rate > 67%",
        }
    ]

    rows = polymarketanalytics.normalize_activity_rows(raw_rows)

    assert rows[0]["trader_wallet"] == "0x94f199fb7789f1aef7fff6b758d6b375100f4c7a"
    assert rows[0]["display_name"] == "KeyTransporter"
    assert rows[0]["side"] == "buy"
    assert rows[0]["shares"] == 430158.73
    assert rows[0]["price"] == 0.63
    assert rows[0]["value"] == 271000.0
    assert rows[0]["event_id"] == "98765"
    assert rows[0]["market_title"] == "Will the next Prime Minister of Hungary be Péter Magyar?"
    assert rows[0]["outcome"] == "Yes"
    assert rows[0]["trade_at"].endswith("+00:00")


def test_build_trader_signals_manifest_filters_tracked_traders_and_sets_source_status():
    leaderboard_rows = polymarketanalytics.normalize_leaderboard_rows(
        [
            {
                "trader": "0xaaaabbbbccccddddeeeeffff1111222233334444",
                "trader_name": "RankOne",
                "overall_gain": 2500000,
                "active_positions": 7,
                "win_amount": 3100000,
                "loss_amount": -600000,
                "win_rate": 0.72,
                "total_current_value": 150000,
                "total_positions": 35,
                "rank": 1,
                "trader_tags": "Overall PnL > $1m",
            },
            {
                "trader": "0xbbbbccccddddeeeeffff11112222333344445555",
                "trader_name": "LowWinRate",
                "overall_gain": 4000000,
                "active_positions": 12,
                "win_amount": 6000000,
                "loss_amount": -2000000,
                "win_rate": 0.55,
                "total_current_value": 210000,
                "total_positions": 65,
                "rank": 2,
                "trader_tags": "",
            },
        ]
    )
    activity_rows = polymarketanalytics.normalize_activity_rows(
        [
            {
                "trade_dttm": "2026-03-26 08:49:29",
                "trader_id": "0xaaaabbbbccccddddeeeeffff1111222233334444",
                "trader_name": "RankOne",
                "side": "buy",
                "amount": 1000,
                "price": 0.63,
                "value": 630.0,
                "event_id": "event-1",
                "market_title": "Will the Fed cut interest rates in June 2026?",
                "market_subtitle": "",
                "outcome": "Yes",
                "trader_tags": "",
            },
            {
                "trade_dttm": "2026-03-26 08:48:29",
                "trader_id": "0xbbbbccccddddeeeeffff11112222333344445555",
                "trader_name": "LowWinRate",
                "side": "buy",
                "amount": 1000,
                "price": 0.50,
                "value": 500.0,
                "event_id": "event-2",
                "market_title": "Will Nvidia finish 2026 above $2,000?",
                "market_subtitle": "",
                "outcome": "Yes",
                "trader_tags": "",
            },
        ]
    )

    manifest = polymarketanalytics.build_trader_signals_manifest(
        leaderboard_rows=leaderboard_rows,
        activity_rows=activity_rows,
        leaderboard_status={"status": "fresh"},
        activity_status={"status": "fresh"},
        generated_at="2026-03-26T16:55:00+08:00",
    )

    assert manifest["as_of"] == "2026-03-26T16:55:00+08:00"
    assert len(manifest["tracked_traders"]) == 1
    assert manifest["tracked_traders"][0]["display_name"] == "RankOne"
    assert len(manifest["recent_trades"]) == 1
    assert manifest["recent_trades"][0]["event_id"] == "event-1"
    assert manifest["source_status"]["status"] == "ok"
    assert manifest["source_status"]["tracked_trader_count"] == 1
    assert manifest["source_status"]["recent_trade_count"] == 1


def test_build_trader_signals_manifest_drops_old_tracked_trades():
    leaderboard_rows = polymarketanalytics.normalize_leaderboard_rows(
        [
            {
                "trader": "0xaaaabbbbccccddddeeeeffff1111222233334444",
                "trader_name": "RankOne",
                "overall_gain": 2500000,
                "active_positions": 7,
                "win_amount": 3100000,
                "loss_amount": -600000,
                "win_rate": 0.72,
                "total_current_value": 150000,
                "total_positions": 35,
                "rank": 1,
                "trader_tags": "Overall PnL > $1m",
            }
        ]
    )
    activity_rows = polymarketanalytics.normalize_activity_rows(
        [
            {
                "trade_dttm": "2026-03-26 08:49:29",
                "trader_id": "0xaaaabbbbccccddddeeeeffff1111222233334444",
                "trader_name": "RankOne",
                "side": "buy",
                "amount": 1000,
                "price": 0.63,
                "value": 630.0,
                "event_id": "event-1",
                "market_title": "Will the Fed cut interest rates in June 2026?",
                "market_subtitle": "",
                "outcome": "Yes",
                "trader_tags": "",
            },
            {
                "trade_dttm": "2026-03-20 08:49:29",
                "trader_id": "0xaaaabbbbccccddddeeeeffff1111222233334444",
                "trader_name": "RankOne",
                "side": "buy",
                "amount": 2000,
                "price": 0.55,
                "value": 1100.0,
                "event_id": "event-2",
                "market_title": "Will Bitcoin finish March above $120k?",
                "market_subtitle": "",
                "outcome": "Yes",
                "trader_tags": "",
            },
        ]
    )

    manifest = polymarketanalytics.build_trader_signals_manifest(
        leaderboard_rows=leaderboard_rows,
        activity_rows=activity_rows,
        leaderboard_status={"status": "fresh"},
        activity_status={"status": "fresh"},
        generated_at="2026-03-26T16:55:00+08:00",
    )

    assert len(manifest["recent_trades"]) == 1
    assert manifest["recent_trades"][0]["event_id"] == "event-1"


def test_select_tracked_traders_keeps_high_pnl_whale_even_with_zero_active_positions():
    leaderboard_rows = polymarketanalytics.normalize_leaderboard_rows(
        [
            {
                "trader": "0x1111111111111111111111111111111111111111",
                "trader_name": "DormantWhale",
                "overall_gain": 8200000,
                "active_positions": 0,
                "win_amount": 9000000,
                "loss_amount": -800000,
                "win_rate": 0.81,
                "total_current_value": 0.0,
                "total_positions": 18,
                "rank": 4,
                "trader_tags": "Politics PnL > $100k",
            },
            {
                "trader": "0x2222222222222222222222222222222222222222",
                "trader_name": "TooWeak",
                "overall_gain": 9100000,
                "active_positions": 22,
                "win_amount": 10000000,
                "loss_amount": -900000,
                "win_rate": 0.54,
                "total_current_value": 800000,
                "total_positions": 240,
                "rank": 5,
                "trader_tags": "Politics PnL > $100k",
            },
        ]
    )

    tracked = polymarketanalytics.select_tracked_traders(leaderboard_rows)

    assert [row["display_name"] for row in tracked] == ["DormantWhale"]


def test_fetch_activity_pages_deeper_until_tracked_wallets_appear(monkeypatch, tmp_path):
    scraper = object.__new__(polymarketanalytics.PolymarketAnalyticsScraper)
    scraper.output_dir = tmp_path
    calls = {"count": 0}

    def _fake_fetch_json(_url, params):
        offset = int(params["offset"])
        calls["count"] += 1
        if offset == 0:
            return {
                "data": [
                    {
                        "trade_dttm": "2026-03-26 08:49:29",
                        "trader_id": "0xaaa",
                        "trader_name": "Noise",
                        "side": "buy",
                        "amount": 10,
                        "price": 0.50,
                        "value": 5.0,
                        "event_id": "event-1",
                        "market_title": "Noise market",
                        "market_subtitle": "",
                        "outcome": "Yes",
                        "trader_tags": "",
                    }
                ]
            }
        if offset == 1:
            return {
                "data": [
                    {
                        "trade_dttm": "2026-03-26 08:48:29",
                        "trader_id": "0xtracked",
                        "trader_name": "Tracked",
                        "side": "buy",
                        "amount": 1000,
                        "price": 0.63,
                        "value": 630.0,
                        "event_id": "event-2",
                        "market_title": "Will the Fed cut interest rates in June 2026?",
                        "market_subtitle": "",
                        "outcome": "Yes",
                        "trader_tags": "",
                    }
                ]
            }
        raise AssertionError("fetch_activity should stop once the tracked wallet is found")

    monkeypatch.setattr(scraper, "_fetch_json", _fake_fetch_json)

    rows, status = polymarketanalytics.PolymarketAnalyticsScraper.fetch_activity(
        scraper,
        pages=5,
        page_size=1,
        tracked_wallets={"0xtracked"},
        target_tracked_hits=1,
        min_pages=1,
    )

    assert calls["count"] == 2
    assert len(rows) == 2
    assert any(row["trader_wallet"] == "0xtracked" for row in rows)
    assert status["status"] == "fresh"
    assert status["row_count"] == 2


def test_fetch_activity_keeps_partial_rows_when_later_page_errors(monkeypatch, tmp_path):
    scraper = object.__new__(polymarketanalytics.PolymarketAnalyticsScraper)
    scraper.output_dir = tmp_path
    calls = {"count": 0}

    def _fake_fetch_json(_url, params):
        offset = int(params["offset"])
        calls["count"] += 1
        if offset == 0:
            return {
                "data": [
                    {
                        "trade_dttm": "2026-03-26 08:49:29",
                        "trader_id": "0xpartial",
                        "trader_name": "Partial",
                        "side": "buy",
                        "amount": 200,
                        "price": 0.51,
                        "value": 102.0,
                        "event_id": "event-partial",
                        "market_title": "Will inflation rise in April 2026?",
                        "market_subtitle": "",
                        "outcome": "Yes",
                        "trader_tags": "",
                    }
                ]
            }
        raise RuntimeError("server 500")

    monkeypatch.setattr(scraper, "_fetch_json", _fake_fetch_json)

    rows, status = polymarketanalytics.PolymarketAnalyticsScraper.fetch_activity(
        scraper,
        pages=3,
        page_size=1,
        min_pages=1,
    )

    assert calls["count"] == 2
    assert len(rows) == 1
    assert rows[0]["event_id"] == "event-partial"
    assert status["status"] == "partial"
    assert status["row_count"] == 1


def test_fetch_tracked_trader_activity_queries_wallet_specific_endpoint(monkeypatch, tmp_path):
    scraper = object.__new__(polymarketanalytics.PolymarketAnalyticsScraper)
    scraper.output_dir = tmp_path
    seen = []

    def _fake_fetch_json(_url, params):
        seen.append(params["trader_id"])
        return {
            "data": [
                {
                    "trade_dttm": "2026-03-26 16:31:00",
                    "trader_id": params["trader_id"],
                    "trader_name": "KeyTransporter",
                    "side": "buy",
                    "amount": 556,
                    "price": 0.7,
                    "value": 389.2,
                    "event_id": "203533",
                    "market_title": "Will the Fed cut interest rates in June 2026?",
                    "market_subtitle": "",
                    "outcome": "Yes",
                    "trader_tags": "",
                }
            ]
        }

    monkeypatch.setattr(scraper, "_fetch_json", _fake_fetch_json)

    rows, status = polymarketanalytics.PolymarketAnalyticsScraper.fetch_tracked_trader_activity(
        scraper,
        tracked_traders=[
            {"wallet": "0xaaa", "display_name": "A"},
            {"wallet": "0xbbb", "display_name": "B"},
        ],
        per_trader_limit=1,
        max_traders=2,
    )

    assert seen == ["0xaaa", "0xbbb"]
    assert len(rows) == 2
    assert rows[0]["trader_wallet"] in {"0xaaa", "0xbbb"}
    assert status["status"] == "fresh"
    assert status["row_count"] == 2


def test_write_run_artifacts_emits_latest_files(tmp_path):
    manifest = {
        "generated_at": "2026-03-26T16:55:00+08:00",
        "as_of": "2026-03-26T16:55:00+08:00",
        "leaderboard_latest": [{"rank": 1, "display_name": "RankOne"}],
        "activity_latest": [{"event_id": "event-1"}],
        "tracked_traders": [{"rank": 1, "display_name": "RankOne"}],
        "recent_trades": [{"event_id": "event-1"}],
        "source_status": {"status": "ok", "tracked_trader_count": 1, "recent_trade_count": 1},
    }

    polymarketanalytics.write_run_artifacts(manifest, output_dir=tmp_path)

    assert json.loads((tmp_path / "leaderboard_latest.json").read_text(encoding="utf-8"))[0]["display_name"] == "RankOne"
    assert json.loads((tmp_path / "activity_latest.json").read_text(encoding="utf-8"))[0]["event_id"] == "event-1"
    saved = json.loads((tmp_path / "trader_signals_latest.json").read_text(encoding="utf-8"))
    assert saved["source_status"]["status"] == "ok"
