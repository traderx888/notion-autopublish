# Telegram Alert Schedule Adjustments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the requested Telegram alert timing changes, add the missing alerts, and align repo/control/scheduler state while clarifying why `newsletter` is not live.

**Architecture:** Keep the three sources of truth aligned: `fundman-jarvis` repo sender definitions, `All-in-one/workflow/cross_repo_tasks.yaml`, and Windows Task Scheduler. For alerts that need multiple run times, prefer distinct task keys per slot instead of overloading one key so the audit layer can track them cleanly. Treat `newsletter` as an existing sender that needs activation and control metadata, not a net-new feature.

**Tech Stack:** Python, batch wrappers, Windows Task Scheduler, Telegram sender helpers, cross-repo task control JSON

---

## Requested Changes

| Change Type | Alert | Current | Requested |
|---|---|---|---|
| Modify | Crypto Daily News | `11:00 HKT` | Keep `11:00 HKT` and add `10:00 HKT` plus `11:40 HKT` |
| Delete | Excel Reminder | `10:00 HKT` | Remove |
| Modify | Southbound Flow | `15:30 HKT` | Add `12:30 HKT` and keep `15:30 HKT` |
| Add | Commodity Model - Live Overlay Report | not scheduled | `09:45 HKT`, `21:45 HKT` |
| Add | GDrive Breadth & Regime Snapshot | not scheduled | `20:45 HKT` |
| Add | Cross-Asset Momentum (1D) | not scheduled | `09:05 HKT`, `11:45 HKT`, `15:45 HKT`, `21:00 HKT` |
| Investigate / Activate | Newsletter | repo-only `11:00 HKT` | Make live, publish to website, send URL to Telegram |

## Current State Notes

- `Crypto Daily News` is a live scheduler task today and is also present in `All-in-one/workflow/cross_repo_tasks.yaml`.
- `Excel Reminder` exists in `fundman-jarvis/daily_reminders.py` and is live in the scheduler, but it is not present in `All-in-one/workflow/cross_repo_tasks.yaml`.
- `Southbound Flow` is live at `15:30 HKT` and already has a control entry.
- `Newsletter` exists in code as `fundman-jarvis/daily_reminders.py -> _send_newsletter_task()`.
- `_send_newsletter_task()` calls `newsletter_generator.main(no_deploy=False)`, which already attempts Netlify deploy and returns a URL when deploy succeeds.
- `Newsletter` is repo-only because there is no active scheduler registration for it and no control-file entry in `All-in-one/workflow/cross_repo_tasks.yaml`.
- The scheduler audit on `2026-03-25` also shows several live jobs that are missing in control; this task should avoid making that drift worse.

## Source Files To Touch

### Control Layer

- Modify: `C:\Users\User\Documents\GitHub\All-in-one\workflow\cross_repo_tasks.yaml`

### Runtime Sender Layer

- Modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\daily_reminders.py`
- Possibly create or modify wrappers in `C:\Users\User\Documents\GitHub\fundman-jarvis\run_*.bat`
- Review: `C:\Users\User\Documents\GitHub\fundman-jarvis\newsletter_generator.py`
- Review for missing alert sources:
  - `C:\Users\User\Documents\GitHub\fundman-jarvis\asset_models\commodity_live_overlay.py`
  - `C:\Users\User\Documents\GitHub\fundman-jarvis\gdrive_reader.py`
  - `C:\Users\User\Documents\GitHub\fundman-jarvis\market_breadth.py`

### Audit / Documentation Layer

- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\telegram_schedule_audit.py`
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\docs\telegram_schedule_audit_flow.md`
- Update generated artifact after verification:
  - `C:\Users\User\Documents\GitHub\notion-autopublish\outputs\ops\telegram_schedule_audit_latest.json`

## Implementation Guidance

### 1. Multi-slot alerts should get distinct task keys

Use separate keys for separate scheduler instances so the audit layer can distinguish them. Candidate naming:

- `crypto_news_daily_1000`
- `crypto_news_daily_1140`
- `southbound_1230`
- `commodity_live_overlay_am`
- `commodity_live_overlay_pm`
- `gdrive_breadth_regime_2045`
- `cross_asset_momentum_0905`
- `cross_asset_momentum_1145`
- `cross_asset_momentum_1545`
- `cross_asset_momentum_2100`

### 2. Excel deletion must remove all three layers

- Remove repo sender metadata if the task is no longer desired.
- Remove or disable the scheduler job.
- Ensure the audit no longer expects it.

### 3. Newsletter activation path

`newsletter` already has the business logic:

- generate content
- deploy to Netlify
- send a Telegram message containing the returned URL or output path

What is missing is operational activation:

- control-file entry
- scheduler registration
- confirmation that Netlify environment variables are available on the scheduled runtime host

### 4. Missing alerts need source confirmation before scheduler work

- `Commodity Model - Live Overlay Report`: likely can be built from `asset_models/commodity_live_overlay.py`, but a Telegram sender path still needs to be identified or created.
- `GDrive Breadth & Regime Snapshot`: likely can reuse `gdrive_reader.py` plus `market_breadth.py`, but a dedicated sender/wrapper is not yet evident from the current audit.
- `Cross-Asset Momentum (1D)`: quick scan found general momentum-related code, but not a dedicated Telegram sender task with this exact name. This needs a source-of-truth definition before timing changes can be implemented safely.

## Verification Commands

Run after implementation:

```powershell
python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish
```

Expected:

- requested alerts appear with the new times
- deleted alerts disappear from live scheduler and repo/control inventory
- `newsletter` moves from `Repo only` to `Live scheduler` if activated

## Evidence Captured

- Live audit rerun on `2026-03-25`
- Output artifact: `C:\Users\User\Documents\GitHub\notion-autopublish\outputs\ops\telegram_schedule_audit_latest.json`

## Implementation Result

- Removed `Excel Reminder` from `fundman-jarvis/daily_reminders.py` and deleted the live `JARVIS-Reminder-excel` scheduler task.
- Kept the legacy `Crypto Daily News` `11:00 HKT` run and added two more live slot-specific jobs:
  - `JARVIS-Reminder-crypto-news-daily`
  - `JARVIS-Reminder-crypto-news-1000`
  - `JARVIS-Reminder-crypto-news-1140`
- Added `southbound_1230` as a distinct `daily_reminders.py` task so the `12:30 HKT` run does not suppress the existing `15:30 HKT` run.
- Activated `newsletter` as a live weekday scheduler job using `daily_reminders.py --task newsletter`.
- Added new sender scripts in `fundman-jarvis` for:
  - `Commodity Model - Live Overlay Report`
  - `GDrive Breadth & Regime Snapshot`
  - `Cross-Asset Momentum (1D)`
- Updated `All-in-one/workflow/cross_repo_tasks.yaml` and `notion-autopublish/tools/telegram_schedule_audit.py` so control and audit state match the requested schedule.

## Verification Result

- `python -m pytest tools/test_telegram_schedule_audit.py -q`
  - Result: `10 passed`
- `python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish`
  - Result: requested tasks now show as `live_scheduler` with no issues:
    - `crypto_news_daily` -> `11:00 HKT`
    - `crypto_news_1000` -> `10:00 HKT`
    - `crypto_news_1140` -> `11:40 HKT`
    - `newsletter` -> `11:00 HKT`
    - `southbound_1230` -> `12:30 HKT`
    - `southbound` -> `15:30 HKT`
    - `commodity_live_overlay_0945` -> `09:45 HKT`
    - `commodity_live_overlay_2145` -> `21:45 HKT`
    - `gdrive_breadth_regime_2045` -> `20:45 HKT`
    - `cross_asset_momentum_0905` -> `09:05 HKT`
    - `cross_asset_momentum_1145` -> `11:45 HKT`
    - `cross_asset_momentum_1545` -> `15:45 HKT`
    - `cross_asset_momentum_2100` -> `21:00 HKT`
  - Removed from the audit inventory as intended:
    - `excel`
