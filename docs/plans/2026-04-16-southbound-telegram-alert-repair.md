# Southbound Flow Telegram Alert Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the `southbound` Telegram alert so the screenshot again includes the southbound chart and visible Eastmoney net-flow data after the source page layout moved.

**Architecture:** Investigate the live Eastmoney DOM/layout change first, then replace the brittle fixed crop logic in `fundman-jarvis/daily_reminders.py` with DOM-driven bounds that anchor on the actual southbound/northbound section container. Lock the regression with focused tests that exercise the crop-bounds resolver separately from Selenium.

**Tech Stack:** Python 3.11, Selenium, Chrome/WebDriver Manager, Pillow, pytest/unittest, Playwright for live page inspection.

---

## Root Cause

- The bad Telegram image from `2026-04-16 15:31 HKT` was not only a crop issue. The saved full screenshot `southbound_full_20260416_153001.png` was a partially rendered Eastmoney page, so the old code still returned `capture_ok` and then cropped the wrong area.
- The old implementation waited only for `document.readyState == "complete"` and then searched for loose title text. When the real `#main_content` layout had not finished rendering, the text query missed the flow section and fell back to a ratio crop, which produced the blank/blue-link image shown in Telegram.
- Live Selenium inspection also showed the Eastmoney DOM shape differs from the previous assumption: `#main_content` now exposes `contentBxzj` and `contentNxzj` as direct children, followed by the涨幅榜 `maincont`, instead of one shared flow wrapper. The crop logic needed to derive bounds from these direct children.

### Task 1: Capture Root Cause Evidence

**Files:**
- Modify: `docs/plans/2026-04-16-southbound-telegram-alert-repair.md`
- Inspect: `../fundman-jarvis/daily_reminders.py`
- Inspect: `../fundman-jarvis/tests/test_daily_reminders.py`

**Step 1: Reproduce on the live Eastmoney page**
Run the existing capture path or inspect the live DOM and identify which selector / bounding logic moved.

**Step 2: Record the failure mode**
Document whether the old logic is anchoring to the wrong header, using stale dimensions, or missing a new wrapper.

### Task 2: Add a Failing Regression Test

**Files:**
- Modify: `../fundman-jarvis/tests/test_daily_reminders.py`
- Modify: `../fundman-jarvis/daily_reminders.py`

**Step 1: Write the failing test**
Add a test for a new southbound crop-bounds helper using representative DOM rects from the current page layout.

**Step 2: Run the focused test to verify it fails**
Run: `python -m pytest tests/test_daily_reminders.py -q -k southbound`
Expected: FAIL because the helper does not exist or returns the stale bounds.

### Task 3: Implement the Minimal Fix

**Files:**
- Modify: `../fundman-jarvis/daily_reminders.py`

**Step 1: Add a DOM-driven southbound bounds resolver**
Compute crop bounds from live section/container rects instead of fixed ratios and stale offsets.

**Step 2: Wire the helper into `_capture_southbound_mid_panel`**
Keep the existing retry/fallback flow unchanged, only replace the brittle crop calculation.

### Task 4: Verify

**Files:**
- Modify: `../fundman-jarvis/tests/test_daily_reminders.py`
- Modify: `docs/plans/2026-04-16-southbound-telegram-alert-repair.md`

**Step 1: Run targeted tests**
Run: `python -m pytest tests/test_daily_reminders.py -q -k southbound`
Expected: PASS.

**Step 2: Run a safe local capture check**
Run the smallest command that exercises `_capture_southbound_mid_panel` or `daily_reminders.py --task southbound --force` without unintended Telegram delivery if the environment allows it.

**Step 3: Record the actual results**
Write the commands and outcomes into this plan file before claiming completion.

## Verification Result

- `python -m pytest tests/test_daily_reminders.py -q -k southbound`
  - Result: `6 passed, 40 deselected`
- `python - <<'PY' ... daily_reminders._capture_southbound_mid_panel(datetime(2026,4,16,19,20,0)) ... PY`
  - Result: returned `C:\Users\User\Documents\GitHub\fundman-jarvis\data\reminder_images\southbound_20260416_192000.png`
  - Visual check: the generated image includes the Eastmoney summary table, both northbound/southbound charts, and the southbound data table; it does not reproduce the blank/blue-link Telegram image.

## Authoritative Files

- `../fundman-jarvis/daily_reminders.py`
- `../fundman-jarvis/tests/test_daily_reminders.py`

## Cross-Repo Note

- This repair changes `fundman-jarvis` screenshot capture behavior only. No upstream artifact schema changed in `notion-autopublish`, and there is no downstream `fundman-jarvis` consumer contract impact beyond the alert image quality fix.
