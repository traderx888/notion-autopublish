# Polymarket Change Alert Focus Filter Implementation Plan

> Superseded on 2026-03-27 by `docs/plans/2026-03-27-polymarket-runtime-reset.md`. This earlier note documented a target state that was not fully wired into the live `fundman-jarvis` sender path.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restrict the Polymarket change alert to market-relevant contracts so Telegram alerts focus on financial markets, crypto, and geopolitics instead of sports, celebrity, or entertainment topics.

**Architecture:** The live `Polymarket Change Alert` logic does not run in `notion-autopublish`; this repo only tracks the scheduler entry. The behavior lives in `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_monitor.py`, so the change should add an explicit relevance filter there, keep history and bridge outputs aligned with that narrower scope, and extend the existing monitor tests to lock the behavior in.

**Tech Stack:** Python 3, `pytest`, `fundman-jarvis` Polymarket monitor + Telegram formatter.

---

### Task 1: Document the cross-repo boundary

**Files:**
- Modify: `docs/plans/2026-03-23-polymarket-change-alert-focus-filter.md`

**Step 1: Record scope**

Note that `notion-autopublish` contains the scheduler audit only, while the runtime implementation is in `fundman-jarvis/polymarket_monitor.py`.

**Step 2: Record downstream consumer**

State that the Telegram `Polymarket Change Alert` and `polymarket_bridge.json` are the downstream consumers affected by the filter.

### Task 2: Write the failing monitor tests in `fundman-jarvis`

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_monitor.py`

**Step 1: Write a failing classification/filter test**

Add a test proving market-relevant categories remain included:
- `rates`
- `macro`
- `crypto`
- `geopolitics`

**Step 2: Write a failing exclusion test**

Add a test proving non-market categories are excluded from the change alert path:
- `politics`
- `tech`
- `other`

Use representative contracts such as:
- `"Fed rate cut in June?"`
- `"Bitcoin above 100k by June?"`
- `"Iran closes Strait of Hormuz?"`
- `"Super Bowl winner 2027"`
- `"Taylor Swift album release?"`

**Step 3: Run the focused tests and verify they fail**

Run: `pytest -q tests/test_polymarket_monitor.py`

Expected: the new tests fail because the current monitor still includes non-market categories.

### Task 3: Implement the relevance filter in `fundman-jarvis`

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_monitor.py`

**Step 1: Add an explicit allowlist**

Introduce a single source of truth such as:

```python
ALERT_RELEVANT_CATEGORIES = {"rates", "macro", "crypto", "geopolitics"}
```

**Step 2: Add a helper**

Add a helper that returns `True` only for contracts whose classified category is in the allowlist.

**Step 3: Apply the filter on the monitor path**

Filter API markets before they are written into the rolling history so the monitor only tracks the relevant subset.

**Step 4: Keep the bridge aligned**

Ensure `build_cross_asset_bridge()` only receives the filtered change set from the monitor run so `polymarket_bridge.json` stays scoped to the same contract universe.

### Task 4: Verify green

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_monitor.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_monitor.py`

**Step 1: Run the focused tests**

Run: `pytest -q tests/test_polymarket_monitor.py`

Expected: PASS

**Step 2: Run the dependent Polymarket workflow tests**

Run: `pytest -q tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py`

Expected: PASS for the touched Polymarket paths.

### Task 5: Handoff note

**Files:**
- Modify: `docs/plans/2026-03-23-polymarket-change-alert-focus-filter.md`

**Step 1: Record verification**

Capture the exact commands run and whether they passed.

**Step 2: Record downstream effect**

State that the `Polymarket Change Alert` and `polymarket_bridge.json` will now exclude non-market categories, with no schema change.

---

## Execution Notes

- Active implementation repo: `C:/Users/User/Documents/GitHub/fundman-jarvis`
- Files changed:
  - `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_monitor.py`
  - `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_tracker.py`
  - `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_monitor.py`
  - `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_tracker.py`
- Behavior change:
  - `Polymarket Change Alert` now tracks `rates`, `macro`, `crypto`, `geopolitics`, `politics`, and `tech`.
  - The hourly `Polymarket Change Alert` Telegram message is now note-style instead of log-style: it opens with `一句看法`, adds a `市場解讀` summary block for the top hourly moves, and ends with a `重點異動` section that keeps the watchlist context in a more readable layout.
  - The hourly `重點異動` section now uses a compact two-line card per move: line 1 is `question | severity`, line 2 combines the key metric and `Watch` assets. This removes the repeated metric dump that still looked like the old log format.
  - The hourly `市場解讀` block is now genuinely interpretive instead of repeating the same headline list. It summarizes theme concentration, topic-wide volume expansion, explicit repricing, and silent accumulation as market meaning.
  - Economic-status contracts such as inflation, recession, unemployment, and explicit `stagflation` classification are included in-scope.
  - The separate `20:05` `Polymarket Active Contracts` reminder now uses the same topic scope in snapshot filtering, active-contract formatting, and short-term analysis.
  - The `20:05` Telegram formatter is now note-style instead of dashboard-style: it opens with `一句看法`, follows with a Chinese `市場解讀` block for the top 1-3 contracts, and ends with a short `重點合約` list showing only the `Yes` probabilities.
  - The `重點合約` section now uses a two-line layout per contract: line 1 shows the contract plus `Yes` probability, line 2 adds `PXxVol`, screenshot `Value`, `1D`, and `5D` so the alert keeps the key context without reverting to a dense table.
  - When the top contracts form a date ladder on the same theme, the formatter writes a sell-side-style thesis sentence and a curve interpretation that frames the market as near-term vs medium-term vs long-term.
  - Sports, celebrity, entertainment, and other non-market contracts remain excluded from the monitor path.
  - `polymarket_bridge.json` keeps the same schema and inherits the narrower contract universe because it is built from the filtered change set.

## Verification Evidence

- Red: `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider`
  - Result: `3 failed, 35 passed`
  - Expected failures:
    - `test_classify_contract_macro`
    - `test_fetch_api_snapshot_filters_to_market_relevant_contracts`
    - `test_detect_changes_includes_politics_contracts_with_large_move`
- Green: `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider`
  - Result: `38 passed`
- Regression check: `python -m pytest -q tests/test_polymarket_monitor.py tests/test_daily_workflow_polymarket.py -p no:cacheprovider`
  - Result: `40 passed`
- Red: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`
  - Result: `3 failed, 4 passed`
  - Expected failures:
    - `test_get_polymarket_active_snapshot_filters_to_market_relevant_scope`
    - `test_format_polymarket_active_telegram_filters_non_market_contracts`
    - `test_analyze_polymarket_short_term_filters_non_market_contracts`
- Green: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`
  - Result: `7 passed`
- Full reminder stack: `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider`
  - Result: `80 passed`

## 2026-03-24 Telegram Readability Refresh

**Goal:** Rework the `20:05` `Polymarket Active Contracts` Telegram output so it is probability-first, easier to scan on mobile, and able to summarize the top 1-3 contracts in narrative language instead of dense metric strings.

**Architecture:** The existing active reminder already enriches screenshot rows with Gamma API matches inside `fundman-jarvis/polymarket_tracker.py`. This pass should keep the existing topic scope filter, preserve the reminder entrypoint, and reshape the formatter so the primary section highlights market-implied probabilities and a short plain-language readout, while raw metrics move into a secondary section.

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_tracker.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_tracker.py`
- Modify: `docs/plans/2026-03-23-polymarket-change-alert-focus-filter.md`

### Task 6: Write the failing formatter tests

**Step 1: Add a probability-first active reminder test**

Lock in that the active Telegram output:
- keeps the `Polymarket Active Contracts` heading
- shows a compact `Top Outlook` section for the first three contracts
- prefers `Yes` probability percentages from the Gamma API when available
- falls back to the screenshot `value` when the API match is missing

**Step 2: Add a plain-language narrative expectation**

Use a ladder-style market fixture to assert that the formatter emits short sentences such as:
- `74% sees ...`
- `63% sees ...`
- `15% sees ...`

The test should prove the output is not only a metric line.

**Step 3: Run the focused tracker tests and verify they fail**

Run: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`

Expected: the new formatter assertions fail against the current leaderboard-style output.

### Task 7: Implement the readability changes

**Step 1: Add probability formatting helpers**

Introduce small helpers in `polymarket_tracker.py` to:
- extract the preferred probability for a contract
- normalize readable percent strings
- turn a contract title into a short sentence stem for Telegram

**Step 2: Rework the active Telegram formatter**

Change the formatter so the message structure becomes:
- header and capture time
- `Top Outlook` narrative bullets for ranks 1-3
- a lighter-weight `Market Board` section with rank, probability, and key supporting metrics

**Step 3: Preserve compatibility**

Keep the current reminder entrypoint and HTML-safe output intact so `daily_reminders.py` does not need API changes.

### Task 8: Verify green and record evidence

**Step 1: Run focused tracker tests**

Run: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`

Expected: PASS

**Step 2: Run the reminder-stack regression**

Run: `python -m pytest -q tests/test_polymarket_tracker.py tests/test_daily_reminders.py tests/test_daily_workflow_polymarket.py -p no:cacheprovider`

Expected: PASS

**Step 3: Record the final evidence here**

Capture the exact commands and actual pass/fail counts after the formatter change lands.

## 2026-03-24 Readability Verification Evidence

- Red: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`
  - Result: `2 failed, 6 passed`
  - Expected failures:
    - `test_format_polymarket_active_telegram_is_standalone`
    - `test_format_polymarket_active_telegram_builds_probability_first_narrative_with_fallback`
- Green: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`
  - Result: `8 passed`
- Reminder regression: `python -m pytest -q tests/test_polymarket_tracker.py tests/test_daily_reminders.py tests/test_daily_workflow_polymarket.py -p no:cacheprovider`
  - Result: `43 passed`
- Full Polymarket stack: `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider`
  - Result: `81 passed`

## 2026-03-24 Chinese Readout Extension

**Goal:** Add a Chinese plain-language `市場解讀` block to the `20:05` `Polymarket Active Contracts` reminder so the top contracts read more like a one-page market note than a raw leaderboard.

**Architecture:** Reuse the probability-first active reminder output in `fundman-jarvis/polymarket_tracker.py`, but add a second descriptive layer after `Top Outlook`. The Chinese block should describe each top contract in sentence form and, when the top entries are a date ladder on the same event, synthesize the curve into a short medium-term vs short-term interpretation.

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_tracker.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_tracker.py`
- Modify: `docs/plans/2026-03-23-polymarket-change-alert-focus-filter.md`

## 2026-03-24 Chinese Readout Verification Evidence

- Red: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`
  - Result: `1 failed, 8 passed`
  - Expected failure:
    - `test_format_polymarket_active_telegram_adds_chinese_market_read_for_ladder_markets`
- Green: `python -m pytest -q tests/test_polymarket_tracker.py -p no:cacheprovider`
  - Result: `9 passed`
- Full Polymarket stack: `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider`
  - Result: `82 passed`

## 2026-03-24 Final Telegram Style Direction

**Decision:** The preferred Telegram output is the second, more human-readable format:
- `一句看法`
- `市場解讀`
- `重點合約`

The earlier `Top Outlook` / `Market Board` version was superseded because it still read too much like a dashboard. The final formatter keeps the same probability source logic, but presents it as a short market note rather than a metric panel.

## 2026-03-24 Hourly Change Alert Refresh

**Goal:** Bring the hourly `Polymarket Change Alert` onto the same readability standard as the active-contract reminder, replacing the raw grouped event log with a short market note that still preserves delta, lookback, and watch-asset context.

**Architecture:** The change-alert path stays in `fundman-jarvis/polymarket_monitor.py`. Detection logic remains unchanged; only the Telegram formatter is restructured into three layers:
- `一句看法`
- `市場解讀`
- `重點異動`

The detailed section keeps change-specific data such as `+pp`, `Vol x avg`, `Yes current vs previous`, and `Watch` assets, but stops dumping the full event list in old grouped blocks.

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/polymarket_monitor.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_polymarket_monitor.py`
- Modify: `docs/plans/2026-03-23-polymarket-change-alert-focus-filter.md`

## 2026-03-24 Hourly Change Alert Verification Evidence

- Red: `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider`
  - Result: `2 failed, 37 passed`
  - Expected failures:
    - `test_format_change_alert_telegram_nonempty`
    - `test_format_change_alert_telegram_note_style_for_multiple_changes`
- Green: `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider`
  - Result: `39 passed`
- Full Polymarket stack: `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider`
  - Result: `83 passed`

## 2026-03-24 Hourly Change Alert Summary Refinement

**Issue:** The first note-style hourly formatter still made `市場解讀` feel too close to `重點異動`, because some summary lines reused individual contract headlines.

**Refinement:** `fundman-jarvis/polymarket_monitor.py` now keeps `市場解讀` at the topic/flow layer only:
- topic concentration
- average volume expansion
- aggregate repricing magnitude
- silent accumulation versus confirmed directional move

This removes individual contract names from the summary block so the alert reads like interpretation first, then cards.

## 2026-03-24 Hourly Thesis Sharpening

**Issue:** Even after the summary block was fixed, `一句看法` still read like an event description instead of a trader note.

**Refinement:** `fundman-jarvis/polymarket_monitor.py` now chooses a sharper first-line thesis based on the dominant pattern:
- repricing: `這不是雜訊...`
- thematic volume cluster: `這不是單一 headline...`
- silent accumulation: `這輪更像先有資金卡位...`

This keeps the first sentence judgmental and decision-oriented, while leaving the evidence and contract cards below.

## 2026-03-24 Sports False Positive Root Cause

**Issue:** An NBA `Rookie of the Year award` contract still appeared in the hourly alert and incorrectly inherited the geopolitics watch list.

**Root cause:** `fundman-jarvis/polymarket_monitor.py` was classifying contracts with raw substring matching (`kw in text`). The geopolitics keyword `war` matched the substring inside `award`, so the sports contract was mislabeled as `geopolitics`. Existing history entries could also preserve that bad label even after classifier changes.

**Fix:**
- switch contract classification to boundary-aware keyword matching
- refresh stored history categories from the current question inside `detect_changes()`
- add regressions proving sports `award` contracts stay `other` and are excluded from alert detection

**Verification:**
- `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider` -> `40 passed`
- `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider` -> `84 passed`

## 2026-03-24 Hard-Fail Sports And Entertainment

**Decision:** Add an explicit denylist ahead of the market-topic classifier so sports, entertainment, and idol contracts fail out even when they contain unrelated allowlist keywords such as country names or politics terms.

**Implementation:** `fundman-jarvis/polymarket_monitor.py` now checks a dedicated excluded-keyword set before category allowlist matching. This covers contracts such as:
- NBA / FIFA / World Cup / Super Bowl / Rookie of the Year / MVP
- album / movie / box office / Grammy / Oscar / concert / tour / idol

**Reason:** This prevents obviously non-market contracts from ever receiving trading-oriented `Watch:` mappings or entering the hourly alert universe.

**Verification:**
- `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider` -> `41 passed`
- `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider` -> `85 passed`

## 2026-03-26 Hourly Alert Role Split And Resend Gate

**Issue 1:** `小結` and `市場解讀` were saying almost the same thing.

**Decision:** Split responsibilities:
- `小結`: one-line thesis only
- `市場解讀`: analyze the top 3 highest-volume changed contracts using current `Yes / No` vote split
- `重點異動`: keep the raw event cards and metrics

**Issue 2:** The same volume-driven politics story kept re-sending across the day even when the top contracts were effectively unchanged.

**Decision:** Add an alert-level signature gate for hourly change alerts.
- If the top change story is the same as the last sent alert, suppress Telegram
- Keep running the monitor and dashboard/bridge update anyway
- A new probability story or a genuinely different change set still sends

**Verification:**
- `python -m pytest -q tests/test_polymarket_monitor.py -p no:cacheprovider` -> `49 passed`
- `python -m pytest -q tests/test_jarvis_alerts.py::test_send_polymarket_change_alerts_respects_monitor_suppression -p no:cacheprovider` -> `1 passed`
- `python -m pytest -q tests/test_polymarket_monitor.py tests/test_polymarket_tracker.py tests/test_daily_workflow_polymarket.py tests/test_daily_reminders.py -p no:cacheprovider` -> `93 passed`
