# Polymarket Runtime Reset Implementation Note

> Downstream consumer: `C:\Users\User\Documents\GitHub\fundman-jarvis`

**Goal:** Reset Polymarket to one coherent fundman/trader pipeline so the live hourly alert, 20:05 reminder, and daily refresh all share the same scope filter, fail-closed send gate, and direct-only trade mapping rules.

**Runtime correction:** Before this reset, the live scheduler entry `run_polymarket_monitor.bat` was still calling the legacy log-style `fundman-jarvis/polymarket_monitor.py`, while `polymarket_tracker.py` still emitted the older active-contract plus short-term-trade-plan path. This note records the runtime truth after the reset.

**Upstream artifacts retained:**
- `scraped_data/polymarketanalytics/leaderboard_latest.json`
- `scraped_data/polymarketanalytics/activity_latest.json`
- `scraped_data/polymarketanalytics/trader_signals_latest.json`

**Downstream changes in `fundman-jarvis`:**
- Added shared scope and denylist logic in `polymarket_scope.py`
- Rebuilt `polymarket_monitor.py` around:
  - boundary-aware category classification
  - fail-closed `telegram_should_send`
  - `telegram_signal_kind`
  - `telegram_signal_signature`
  - `telegram_suppression_reason`
  - `trader_source_status`
- Rebuilt the hourly formatter into:
  - `為何現在要看`
  - `Sharp Money`
  - `市場佐證`
  - `交易映射` only when direct mapping confidence is high
- Removed the old scheduler behavior that sent simply because `high_changes > 0`
- Aligned `polymarket_tracker.py`, `daily_reminders.py`, and `daily_workflow.py` to the same filtered in-scope universe
- Kept `polymarket_bridge.json` schema stable, but `top_movers` now reflects only in-scope markets

**Filter rules now applied across all Polymarket flows:**
- Hard denylist first for sports, entertainment, celebrity, idol, weather, and culture/human-interest contracts
- Boundary-aware matching prevents false positives like `award` matching `war`
- Allowed categories remain:
  - `rates`
  - `macro`
  - `crypto`
  - `geopolitics`
  - `politics`
  - `tech`
- Generic politics personality markets no longer receive blanket `Watch:` asset mappings

**Verification:**
- `python -m pytest -q tests\test_polymarket_tracker.py tests\test_polymarket_monitor.py tests\test_polymarket_trader_signal.py tests\test_daily_workflow_polymarket.py tests\test_daily_reminders.py tests\test_jarvis_alerts.py -p no:cacheprovider`
  - `61 passed`
- `python -m py_compile C:\Users\User\Documents\GitHub\fundman-jarvis\polymarket_scope.py C:\Users\User\Documents\GitHub\fundman-jarvis\polymarket_monitor.py C:\Users\User\Documents\GitHub\fundman-jarvis\polymarket_tracker.py C:\Users\User\Documents\GitHub\fundman-jarvis\daily_reminders.py C:\Users\User\Documents\GitHub\fundman-jarvis\daily_workflow.py C:\Users\User\Documents\GitHub\fundman-jarvis\jarvis_alerts.py`
  - passed
- `cmd /c C:\Users\User\Documents\GitHub\fundman-jarvis\run_polymarket_monitor.bat`
  - `Markets: 400 | Relevant: 146 | Changes: 7 (1 HIGH)`
  - `Telegram suppressed: no_high_value_signal`
- `python polymarket_monitor.py`
  - `Markets: 400 | Relevant: 146 | Changes: 10 (1 HIGH)`
  - `Telegram suppressed: no_high_value_signal`
- `python - <<live active snapshot smoke>>`
  - active reminder formatter returned `No in-scope Polymarket contracts were extracted.` for that screenshot cycle, so no sports contract leaked through the reminder output
- `python - <<gamma top relevant spot check>>`
  - first five relevant markets were `crypto`, `geopolitics`, `geopolitics`, `politics`, `tech`; no NBA/NHL terms appeared

**Operational note:** If the upstream trader artifact is stale or empty, the hourly monitor now falls back to the stricter repricing path. If no sharp-money or high-conviction repricing story exists, Telegram sends nothing and only dashboard/bridge continue to update.
