# MacroMicro Manual Network Recorder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a manual, headed MacroMicro network recorder that uses the real Chrome-backed session to capture the actual XHR/JSON endpoints for selected target pages.

**Architecture:** Keep the existing scrape flow intact and add a separate recorder path in the MacroMicro scraper plus a CLI flag. The recorder will attach response listeners, let the user interact with each target page manually, then write a summary manifest and raw per-target capture files so later work can build cookie-backed API fetchers.

**Tech Stack:** Python, Playwright sync API, persistent Chrome-backed profile, pytest

---

### Task 1: Define Recorder Output Contract

**Files:**
- Modify: `tests/test_macromicro_scraper.py`

**Step 1: Write the failing test**

Add tests for:
- building a per-target recorder payload from captured responses
- writing manifest + raw capture artifact files
- CLI routing for `--record-network`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: FAIL because the recorder helpers and CLI mode do not exist yet.

### Task 2: Add Recorder Helpers

**Files:**
- Modify: `browser/scrapers/macromicro.py`

**Step 1: Write minimal implementation**

Add pure helpers to:
- summarize captured JSON responses
- build a per-target recorder payload including selected endpoint and extracted payload preview
- write per-target recorder summary + raw capture artifacts

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: the new helper tests pass.

### Task 3: Add Manual Recorder Runtime Path

**Files:**
- Modify: `browser/scrapers/macromicro.py`

**Step 1: Write minimal implementation**

Add `record_network()` and target-level recorder logic that:
- runs headed only
- ensures the session exists
- opens the target page
- listens for XHR/fetch responses
- pauses for manual interaction
- writes artifacts under `scraped_data/macromicro/network_recordings`

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: recorder helper tests stay green.

### Task 4: Wire CLI Entry Point

**Files:**
- Modify: `scrape_macromicro.py`
- Test: `tests/test_macromicro_scraper.py`

**Step 1: Write minimal implementation**

Add `--record-network` so the CLI routes to `record_network()` instead of `run()`. Force headed mode for this path even if `--headless` is supplied.

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: CLI routing test passes.

### Task 5: Verify Runtime Integrity

**Files:**
- Modify: none

**Step 1: Run focused verification**

Run:
- `pytest tests/test_macromicro_scraper.py -q`
- `python -m py_compile browser/scrapers/macromicro.py scrape_macromicro.py`

**Step 2: Confirm output**

Expected: all tests pass, no syntax errors.
