# FinTwit Author Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh the FinTwit monitor account list so the X/Twitter scrape targets current, fetchable external author handles and rerun the workflow against the updated config.

**Architecture:** Keep the monitor pipeline unchanged and only refresh the source-of-truth account entries in `config/fintwit_monitor.json`. Validate replacement handles through the same `xreach` fetch path used by `monitor_fintwit.py`, then run the workflow and record the resulting artifact/log evidence.

**Tech Stack:** Python 3.11+, `monitor_fintwit.py`, `npx xreach`, repo `.env`, JSON config, Telegram workflow logging.

---

### Task 1: Audit the stale scrape handles

**Files:**
- Read: `config/fintwit_monitor.json`
- Read: `outputs/ops/fintwit_monitor.log`

**Step 1:** Identify handles that have repeated `xreach` failures or persistent `0 tweets` results.

**Step 2:** Validate candidate replacements with `npx.cmd xreach tweets @handle -n 1 --json` using the repo `.env`.

**Step 3:** Record only validated replacements in the config update.

### Task 2: Refresh the source-of-truth config

**Files:**
- Modify: `config/fintwit_monitor.json`

**Step 1:** Replace typoed or stale handles with validated working handles:
- `chaaborsi` -> `chamath`
- `BobEUnlworthy` -> `BobEUnlimited`
- `HindsightPete` -> `Peter_Atwater`
- `MuddyWatersRes` -> `muddywatersre`
- `ClarityToast` -> `jessefelder`
- `FedGuy12` -> `josephwang`
- `TastyEddy` -> `Hedgeye`

**Step 2:** Remove entries that could not be validated as current scrape targets and already have overlapping coverage:
- `biaborsi`
- `zaborniki`

### Task 3: Rerun and verify the workflow

**Files:**
- Read/refresh: `scraped_data/twitter/fintwit_scored_latest.json`
- Read/refresh: `scraped_data/twitter/fintwit_state.json`
- Read/append: `outputs/ops/fintwit_monitor.log`

**Step 1:** Run `python monitor_fintwit.py --dry-run --backfill` to confirm the updated author list fetches and scores correctly without sending alerts.

**Step 2:** Run `python monitor_fintwit.py` to execute the actual workflow once with the refreshed config.

**Step 3:** Record the exact commands and outcomes in the final handoff/summary, including whether any alerts were sent and the artifact paths updated.
