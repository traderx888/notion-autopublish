# Polymarket Holiday Handoff Note

> Downstream runtime owner: `C:\Users\User\Documents\GitHub\fundman-jarvis`

## Purpose

This note turns the recent Polymarket work into a holiday-safe handoff package.
The goal is to let another operator run and debug the Polymarket pipeline on a
different machine without depending on chat history or one local workstation.

## Source of Truth

Use this order of truth:

1. Private GitHub repos for `notion-autopublish` and `fundman-jarvis`
2. Dated implementation notes and handoffs in `docs/`
3. Local `.env` files created from committed `.env.example`
4. Secrets stored in a vault or password manager

Raw chat is not a runtime artifact and must not be treated as the canonical
handoff.

## Current Polymarket System Split

- `notion-autopublish`
  - owns upstream scraping and structured artifacts
  - current upstream Polymarket trader artifacts:
    - `scraped_data/polymarketanalytics/leaderboard_latest.json`
    - `scraped_data/polymarketanalytics/activity_latest.json`
    - `scraped_data/polymarketanalytics/trader_signals_latest.json`
- `fundman-jarvis`
  - owns the live monitor, reminder, bridge, and Telegram sender
  - authoritative runtime files:
    - `polymarket_scope.py`
    - `polymarket_monitor.py`
    - `polymarket_tracker.py`
    - `daily_reminders.py`
    - `daily_workflow.py`
    - `jarvis_alerts.py`

## Decisions To Preserve

- Sports, entertainment, celebrity, idol, weather, and generic human-interest
  contracts are denylisted before any Telegram signal logic.
- The hourly `Polymarket Change Alert` is fail-closed. If there is no real
  high-value `sharp_money` or `repricing` story, Telegram sends nothing.
- Generic politics personality markets do not get blanket `Watch:` mappings.
  Trade mapping is direct-only.
- `fundman-jarvis` is the live sender. `notion-autopublish` is upstream support,
  not the live Polymarket source of truth.
- GitHub is canonical. Localhost state is disposable unless it is committed or
  documented.

## What The Workmate Should Read First

1. This note
2. `docs/plans/2026-03-27-polymarket-runtime-reset.md`
3. `C:\Users\User\Documents\GitHub\fundman-jarvis\docs\architecture\polymarket-operator-runbook.md`
4. `C:\Users\User\Documents\GitHub\fundman-jarvis\docs\handoffs\2026-03-27-polymarket-holiday-coverage.md`

## Machine Setup Rule

The receiving operator should keep both repos on the same machine and set
`NOTION_AUTOPUBLISH_DIR` in `fundman-jarvis/.env` if the repos are not checked
out as siblings under one parent directory.

## Known Limitations To Call Out

- The 20:05 reminder still depends on local screenshot availability and vision
  extraction credentials.
- The trader artifact can be valid but empty when no recent top-trader public
  activity matches the monitoring window.
- Live verification must distinguish between safe preview commands and actual
  send commands.

## Holiday Coverage Default

- Keep both repos synced through private GitHub.
- Let each operator use a local `.env` on their own machine.
- Share secrets only through a vault or password manager.
- Before changing runtime logic, update the handoff note first if live behavior
  differs from the current documented state.
