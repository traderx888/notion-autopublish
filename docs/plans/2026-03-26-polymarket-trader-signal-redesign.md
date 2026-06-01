# Polymarket Trader Signal Redesign Implementation Note

> Superseded on 2026-03-27 by `docs/plans/2026-03-27-polymarket-runtime-reset.md`. This note described the intended trader-first runtime, but the live `fundman-jarvis` sender was still running the legacy hourly monitor and reminder paths until the runtime reset was applied.

> Downstream consumer: `C:\Users\User\Documents\GitHub\fundman-jarvis`

**Goal:** Replace the current Polymarket hourly Telegram alert with a higher-urgency hybrid signal built from public top-trader activity first and direct-market repricing second.

**Architecture:** `notion-autopublish` owns the new public `polymarketanalytics.com` scrape and emits stable JSON artifacts under `scraped_data/polymarketanalytics/`. `fundman-jarvis` consumes `trader_signals_latest.json`, combines it with the existing Gamma-based repricing monitor, and only sends Telegram when a new sharp-money or major repricing story is detected.

**Artifacts:**
- `scraped_data/polymarketanalytics/leaderboard_latest.json`
- `scraped_data/polymarketanalytics/activity_latest.json`
- `scraped_data/polymarketanalytics/trader_signals_latest.json`

**Contract notes:**
- `trader_signals_latest.json` fields: `generated_at`, `as_of`, `tracked_traders`, `recent_trades`, `source_status`
- `fundman-jarvis` keeps `polymarket_bridge.json` schema stable in this pass
- downstream monitor additions in `fundman-jarvis/polymarket_monitor.py`:
  - `telegram_signal_kind`
  - `telegram_signal_signature`
  - `telegram_suppression_reason`
  - `trader_source_status`

**Implemented files:**
- upstream:
  - `browser/scrapers/polymarketanalytics.py`
  - `scrape_polymarketanalytics.py`
- downstream consumer:
  - `fundman-jarvis/external_scrapers.py`
  - `fundman-jarvis/polymarket_monitor.py`
  - `fundman-jarvis/jarvis_alerts.py`
  - `fundman-jarvis/tests/test_polymarket_trader_signal.py`
  - `fundman-jarvis/tests/test_jarvis_alerts.py`

**Behavior changes shipped:**
- upstream scraper now pulls public JSON directly from `polymarketanalytics.com` and writes the three latest artifacts without depending on fragile page selectors
- tracked traders are filtered by `win_rate_pct >= 60` with `active_positions` treated as a soft preference instead of a hard gate
- top-PnL traders with low current active positions are still tracked when they have enough historical position count / realized edge
- upstream now uses two activity sources:
  - deep public global activity pagination
  - targeted public `trader_id=` activity pulls for tracked wallets
- `recent_trades` is now a true recent window, filtered to the last 24 hours before being handed to `fundman-jarvis`
- later-page API failures no longer discard already-collected activity rows; partial activity results are preserved
- downstream hourly alert is no longer "all changed contracts"
- downstream signal priority is now:
  - `sharp_money`: tracked public trader activity on in-scope markets
  - `repricing`: only high-conviction Yes/No repricing fallback
- Telegram sends only when a new signal signature appears; same story is suppressed while dashboard/bridge still update
- `交易映射` only appears for direct macro / crypto / energy mappings and is omitted for generic politics personality markets

**Verification targets:**
- `python -m pytest -q tests/test_polymarketanalytics_scraper.py -p no:cacheprovider`
- `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_trader_signal.py tests/test_jarvis_alerts.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider`
- `python scrape_polymarketanalytics.py --headless`

**Verification results:**
- `python -m pytest -q tests/test_polymarketanalytics_scraper.py -p no:cacheprovider`
  - `9 passed`
- `python -m pytest -q C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_polymarket_trader_signal.py C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_polymarket_monitor.py C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_jarvis_alerts.py C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_daily_workflow_polymarket.py C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_daily_reminders.py -p no:cacheprovider`
  - `101 passed`
- `python scrape_polymarketanalytics.py --headless --force-leaderboard --activity-pages 1 --activity-page-size 25`
  - produced fresh `leaderboard_latest.json`, `activity_latest.json`, and `trader_signals_latest.json`
  - smoke result: `tracked_trader_count=25`, `recent_trade_count=0`, `source_status=ok`
- `python -m pytest -q tests/test_polymarket_monitor.py tests/test_jarvis_alerts.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider`
  - `97 passed`
- upstream live smoke after depth + targeted trader fetch:
  - `tracked_trader_count=25`
  - `recent_trade_count=0`
  - `activity_status=fresh`
  - `tracked_activity_status=fresh`
  - interpretation: the pipeline now reaches tracked wallets correctly, but there were still no tracked-wallet public trades inside the 24h urgency window on the smoke run
- downstream dry-run:
  - live `run_polymarket_monitor()` returned `success=true`, `telegram_signal_kind=""`, `telegram_should_send=false`, `telegram_suppression_reason="no_high_value_signal"`, `trader_source_status.status="ok"`
  - deterministic suppression dry-run returned `kind="sharp_money"`, `first_send=true`, `repeat_send=false`
