# Polymarket Geopolitics Alert Now Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate the live Polymarket war/geopolitics alert path, fix any classifier leak that pollutes the geopolitics bucket, and send a Telegram alert immediately only if a true geopolitics mover remains after the fix.

**Architecture:** `notion-autopublish` records the task plan and cross-repo boundary, but the live Polymarket runtime is in `C:\Users\User\Documents\GitHub\fundman-jarvis\polymarket_monitor.py`. The implementation should add a regression test for sports contracts that contain country or war-adjacent keywords, fix the classifier with the smallest safe change, rerun the live monitor, and only send Telegram when the filtered change set still contains a real `geopolitics` move.

**Tech Stack:** Python 3, `pytest`, `fundman-jarvis` Polymarket monitor, Telegram Bot sender.

---

### Task 1: Record the cross-repo runtime scope

**Files:**
- Create: `docs/plans/2026-04-13-polymarket-geopolitics-alert-now.md`

**Step 1: State runtime ownership**

Record that this repo owns the plan and upstream context, while the live sender logic is in `fundman-jarvis/polymarket_monitor.py`.

**Step 2: State downstream consumer**

Record that the downstream consumer is the Telegram `Polymarket Change Alert`, with `data/polymarket_bridge.json` affected only as a freshness artifact and not via schema change.

### Task 2: Add a failing regression in `fundman-jarvis`

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_polymarket_monitor.py`

**Step 1: Write the failing test**

Add a regression asserting that `Will Iran win the 2026 FIFA World Cup?` classifies as `sports`, not `geopolitics`.

**Step 2: Verify red**

Run: `python -m pytest -q tests/test_polymarket_monitor.py -k classify_contract -p no:cacheprovider`

Expected: the new regression fails because country keywords currently outrank the sports deny path.

### Task 3: Implement the minimal classifier fix

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\polymarket_monitor.py`

**Step 1: Add an explicit deny path**

Make sports-style contracts short-circuit before geopolitics keyword matching.

**Step 2: Keep scope unchanged otherwise**

Do not change the alert schema or other category behavior; only stop the false-positive leak into `geopolitics`.

**Step 3: Verify green**

Run: `python -m pytest -q tests/test_polymarket_monitor.py -k classify_contract -p no:cacheprovider`

Expected: PASS

### Task 4: Re-run the live monitor and decide Telegram send

**Files:**
- Modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\data\polymarket_monitor_history.json`
- Modify: `C:\Users\User\Documents\GitHub\fundman-jarvis\data\polymarket_bridge.json`

**Step 1: Run the live monitor**

Run the production monitor and inspect only `geopolitics` changes after the classifier fix.

**Step 2: Send only if qualified**

If the live `geopolitics` slice still contains a real war/geopolitics mover, send the Telegram alert immediately. If not, do not send unrelated noise.

### Task 5: Record evidence

**Files:**
- Modify: `docs/plans/2026-04-13-polymarket-geopolitics-alert-now.md`

**Step 1: Capture verification**

Append the exact commands run and the actual outcomes.

**Step 2: Capture operational result**

Record whether Telegram was sent or intentionally suppressed because no true geopolitics move remained.

## Verification Evidence

- Red: `python -m pytest -q tests/test_polymarket_monitor.py -k classify_contract -p no:cacheprovider`
  - Result: `1 failed, 5 passed, 23 deselected`
  - Expected failure:
    - `test_classify_contract_sports_beats_country_keyword`
- Green subset: `python -m pytest -q tests/test_polymarket_monitor.py -k classify_contract -p no:cacheprovider`
  - Result: `6 passed, 23 deselected`
- Green full file: `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider`
  - Result: `29 passed`
- Live check before fix: `python polymarket_monitor.py`
  - Result: `Markets: 400 | Changes: 124 (43 HIGH)`
  - Operational note: the run surfaced a false-positive geopolitics mover, `Will Iran win the 2026 FIFA World Cup?`, which exposed the classifier leak.
- Live check after fix: inline `python` call to `run_polymarket_monitor()`
  - Result:
    - `success=true`
    - `markets_fetched=400`
    - `changes_detected=121`
    - `high_changes=41`
    - `geo_total=0`
    - `geo_high=0`

## Operational Result

- Telegram not sent.
- Reason: after the classifier fix removed the sports false positive, the live Polymarket change set contained no true `geopolitics` movers to alert on.
- Downstream impact:
  - Runtime repo: `C:\Users\User\Documents\GitHub\fundman-jarvis`
  - Changed runtime files:
    - `polymarket_monitor.py`
    - `tests/test_polymarket_monitor.py`
  - Artifact freshness only:
    - `data/polymarket_monitor_history.json`
    - `data/polymarket_bridge.json`
  - Schema change: none
