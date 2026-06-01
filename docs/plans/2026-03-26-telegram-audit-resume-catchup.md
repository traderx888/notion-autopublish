# Telegram Audit Resume Catch-Up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Telegram schedule audit send once its missed daily alert as soon as the machine or network comes back, without duplicating the same day's audit alert.

**Architecture:** Keep the existing `JARVIS-Reminder-schedule-audit` task as the single alert source. Add a small delivery-state file plus a recovery-aware send mode in `notion-autopublish/tools/telegram_schedule_audit.py`, then update the live `fundman-jarvis` launcher and Windows scheduler repetition so the same task can retry safely after a missed or failed `06:15 HKT` run.

**Tech Stack:** Python, Windows Task Scheduler, cross-repo task control JSON, batch wrappers

---

### Task 1: Document the runtime policy

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\All-in-one\workflow\cross_repo_tasks.yaml`
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\docs\plans\2026-03-26-telegram-audit-resume-catchup.md`

**Steps:**
1. Add a visible catch-up policy to `JARVIS-Reminder-schedule-audit` in the shared control file.
2. Record the intended same-day catch-up behavior and scheduler retry expectation in this plan note.

### Task 2: Add failing tests for missed-slot recovery

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\test_telegram_schedule_audit.py`
- Test: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\test_telegram_schedule_audit.py`

**Steps:**
1. Add a failing test that proves a same-day `Mon-Fri 06:15 HKT` audit slot should send when it was missed and no successful delivery state exists.
2. Add a failing test that proves the recovery mode skips once the same day's slot is already marked as sent.
3. Run the focused pytest selection and confirm the new tests fail for the expected reason.

### Task 3: Implement recovery-aware audit delivery

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\telegram_schedule_audit.py`

**Steps:**
1. Add helpers to read the schedule-audit catch-up policy from `All-in-one/workflow/cross_repo_tasks.yaml`.
2. Add helpers to compute the due slot for `Daily` and `Mon-Fri` schedules in HKT.
3. Add a small JSON state file under `outputs/ops/` that records the last successfully sent slot and last attempt metadata.
4. Add a CLI flag for recovery-aware sending so repeated scheduler runs send only when today's due slot is still unsent.
5. Keep the existing direct `--send` behavior intact for explicit/manual runs.

### Task 4: Wire the live launcher and scheduler retry behavior

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\run_schedule_audit.bat`
- Optional modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\schedule_audit_bridge.py`

**Steps:**
1. Update the live launcher so the scheduled audit uses the recovery-aware send flag.
2. Reconfigure the existing Windows task `JARVIS-Reminder-schedule-audit` to retry through the day instead of firing only once.
3. Preserve the task name so the audit inventory still resolves to the same `schedule_audit` key.

### Task 5: Verify end-to-end behavior and record evidence

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\docs\plans\2026-03-26-telegram-audit-resume-catchup.md`
- Artifact: `C:\Users\User\Documents\GitHub\notion-autopublish\outputs\ops\telegram_schedule_audit_latest.json`

**Steps:**
1. Run `python -m pytest tools\test_telegram_schedule_audit.py -q`.
2. Run `python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish`.
3. Inspect the live scheduler task with `schtasks /Query /TN "JARVIS-Reminder-schedule-audit" /V /FO LIST`.
4. Record the exact commands and outcomes in this plan note.

## Implementation Result

- Added recovery-aware delivery gating to `notion-autopublish/tools/telegram_schedule_audit.py`.
- Added a delivery state file path at `notion-autopublish/outputs/ops/telegram_schedule_audit_delivery_state.json`.
- Added test coverage for:
  - same-day missed-slot recovery
  - duplicate-send suppression after the slot is already marked sent
- Updated `fundman-jarvis/run_schedule_audit.bat` to call the audit with `--send-missed-on-resume`.
- Updated `All-in-one/workflow/cross_repo_tasks.yaml` to document the schedule-audit catch-up policy:
  - `catchup_on_resume: true`
  - `catchup_window_hours: 18`
- Reconfigured the live Windows task `JARVIS-Reminder-schedule-audit` to repeat every `15` minutes for `17:45` after the `06:15 HKT` weekday start time.

## Verification Result

- `python -m pytest tools\test_telegram_schedule_audit.py -q`
  - Result: `12 passed`
- `python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish`
  - Result: audit artifact refreshed successfully at `outputs/ops/telegram_schedule_audit_latest.json`
- Inline decision check:
  - Command: `resolve_resume_catchup_decision(... now=2026-03-26 09:00 HKT ...)`
  - Result: `{'should_send': True, 'reason': 'missed_slot_unsent', 'slot_time_hkt': '2026-03-26T06:15:00+08:00', ...}`
- `schtasks /Query /TN "JARVIS-Reminder-schedule-audit" /V /FO LIST`
  - Result:
    - `Repeat: Every: 0 Hour(s), 15 Minute(s)`
    - `Repeat: Until: Duration: 17 Hour(s), 45 Minute(s)`
