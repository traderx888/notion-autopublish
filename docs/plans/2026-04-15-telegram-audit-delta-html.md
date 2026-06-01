# Telegram Audit Delta HTML Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce schedule-audit Telegram noise by generating an HTML report artifact, sending only a single report link for changed critical issues, and fixing false scheduler drift caused by AM/PM parsing.

**Architecture:** Keep the full JSON and rich local audit report in `notion-autopublish`, then add a second delivery layer tailored for Telegram. That delivery layer renders an HTML artifact, computes a fingerprint from critical issue tuples, and sends one ops-only notification that links to the latest HTML report instead of chunking the full checklist into many messages.

**Tech Stack:** Python, Windows Task Scheduler, Telegram Bot API, cross-repo task control JSON, HTML artifact rendering

---

### Task 1: Lock the contract

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\All-in-one\workflow\cross_repo_tasks.yaml`
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\docs\plans\2026-04-15-telegram-audit-delta-html.md`

**Steps:**
1. Add the schedule-audit delivery policy fields to the shared control entry.
2. Record the expected Telegram behavior and HTML artifact path in this plan note.

### Task 2: Add failing tests first

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\test_telegram_schedule_audit.py`
- Test: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\test_telegram_schedule_audit.py`

**Steps:**
1. Add a failing test that proves scheduler `PM` times normalize to 24-hour HKT strings.
2. Add a failing test that proves non-zero scheduler results are promoted into a critical runtime issue.
3. Add a failing test that proves the Telegram payload is a single HTML-report link rather than a long checklist body.
4. Add a failing test that proves identical critical fingerprints do not send again.

### Task 3: Implement the audit runtime changes

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\telegram_schedule_audit.py`
- Optional modify: `C:\Users\User\Documents\GitHub\notion-autopublish\tools\telegram_hub.py`

**Steps:**
1. Decode `schtasks` output from bytes with explicit fallback logic.
2. Parse `AM` and `PM` scheduler times correctly.
3. Capture scheduler run health metadata and classify critical runtime failures.
4. Render the latest audit HTML artifact beside the JSON artifact.
5. Build a compact Telegram notification that links to the HTML report.
6. Store and compare the last-sent critical fingerprint to suppress repeats.
7. Enforce ops-only routing for this audit and skip delivery if ops credentials are unavailable.

### Task 4: Verify and record evidence

**Files:**
- Artifact: `C:\Users\User\Documents\GitHub\notion-autopublish\outputs\ops\telegram_schedule_audit_latest.html`
- Artifact: `C:\Users\User\Documents\GitHub\notion-autopublish\outputs\ops\telegram_schedule_audit_delivery_state.json`

**Steps:**
1. Run `python -m pytest tools\test_telegram_schedule_audit.py -q`.
2. Run the audit without `--send` and confirm the JSON and HTML artifacts refresh.
3. Run targeted inspection of the generated delivery state fields.
4. Record the exact commands and outcomes in the final handoff.

## Verification Result

- `python -m pytest tools\test_telegram_schedule_audit.py -q`
  - Result: `18 passed`
- `python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish --only-issues`
  - Result: live scheduler query completed without the prior decode crash; refreshed:
    - `outputs/ops/telegram_schedule_audit_latest.json`
    - `outputs/ops/telegram_schedule_audit_latest.html`
- Inline delivery check with the refreshed JSON artifact
  - Result: a single 7-line Telegram HTML message is produced with one report link, not multi-chunk checklist spam
