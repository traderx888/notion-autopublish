# Telegram Alert Ownership And Cross-Asset Repair

**Date:** 2026-04-15
**Owner:** Codex

## Goal

Restore `cross_asset_momentum` Telegram delivery without disturbing the rest of the shared routing setup, and make the repo boundaries easier to operate.

## Decision

- `jarvis-alerts` remains the shared routing and delivery repo.
- `All-in-one/workflow/cross_repo_tasks.yaml` remains the human-readable task inventory.
- Producer repos continue to own sender scripts and scheduler targets.

## Implementation Notes

- Added `fundman-jarvis/send_cross_asset_momentum.py` as the scheduled entrypoint for the four HKT slots.
- Kept the existing cross-asset content alert format intact by wrapping the current sender flow in `telegram_alerts.alert_context`.
- Updated `notion-autopublish/tools/telegram_schedule_audit.py` so repo discovery and runtime metadata use `send_cross_asset_momentum.py --slot ...`.
- Added `All-in-one/workflow/telegram_alert_owner_map.md` as the operator runbook for “which repo do I open?”

## Verification Target

- `python -m pytest tests\test_send_cross_asset_momentum.py -q`
- `python -m pytest tools\test_telegram_schedule_audit.py -q`
- `python check_alert_routing.py cross_asset_momentum_0905`
- `python send_cross_asset_momentum.py --slot 0905 --dry`

## Verification Result

- `python -m pytest tests\test_send_cross_asset_momentum.py -q`
  - Result: `4 passed`
- `python -m pytest tools\test_telegram_schedule_audit.py -q`
  - Result: `18 passed`
- `python -m pytest tests\test_telegram_alerts.py -q`
  - Result: `12 passed`
- `python -m pytest tests\test_acceptance_cli.py -q -k cross_asset_momentum_help`
  - Result: `1 passed`
- `python check_alert_routing.py cross_asset_momentum_0905`
  - Result: route resolves to `primary` plus `shared_drive`; Telegram credentials present
- `python send_cross_asset_momentum.py --slot 0905 --dry`
  - Result: scan completed, scored 24 assets, refreshed `fundman-jarvis/data/momentum_snapshot.json` and `fundman-jarvis/data/momentum_tv_watchlist.txt`, no Telegram send attempted
- `python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish --only-issues`
  - Result: refreshed `outputs/ops/telegram_schedule_audit_latest.json` and `.html`; `cross_asset_momentum_*` no longer appears under `missing_in_repo`, but still shows `runtime_failure` until the repaired scheduled tasks run successfully
