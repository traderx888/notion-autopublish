# MacroMicro Cookie-Backed Fetcher Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a cookie-backed MacroMicro fetcher for `fear-and-greed` and `global-recession-rate` so the normal scraper can pull the known API endpoints directly without manual network recording.

**Architecture:** Reuse the existing Playwright persistent session to derive authenticated request state, fetch the known MacroMicro API endpoints directly, and feed those payloads through the existing deterministic network parsers. Keep the `scrape_macromicro.py` interface and `macromicro_latest.json` artifact stable so `fundman-jarvis` does not need new wrapper code.

**Tech Stack:** Python, Playwright sync API, pytest

---

### Task 1: Lock Direct-Fetch Behavior With Tests

**Files:**
- Modify: `tests/test_macromicro_scraper.py`

**Step 1: Write the failing test**

Add tests for:
- direct cookie-fetch payload generation for `fear-and-greed`
- direct cookie-fetch payload generation for `global-recession-rate`
- `run()` preferring cookie fetch for supported targets
- `run()` falling back to page capture when direct fetch fails

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: FAIL because direct fetch helpers do not exist.

### Task 2: Add Cookie-Fetch Helpers

**Files:**
- Modify: `browser/scrapers/macromicro.py`

**Step 1: Write minimal implementation**

Add:
- known endpoint registry for the two supported targets
- direct-fetch payload builder using existing parsers
- authenticated API request helper that reuses Playwright session state

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: helper-level tests pass.

### Task 3: Integrate Into Main Run Path

**Files:**
- Modify: `browser/scrapers/macromicro.py`

**Step 1: Write minimal implementation**

Update `run()` so:
- supported targets try cookie-backed fetch first
- unsupported/custom targets keep browser capture
- cookie-fetch exceptions fall back to `_capture_target()`

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: run-path tests pass.

### Task 4: Verify Compatibility

**Files:**
- Modify: none

**Step 1: Run focused verification**

Run:
- `pytest tests/test_macromicro_scraper.py -q`
- `python -m py_compile browser/scrapers/macromicro.py scrape_macromicro.py`

**Step 2: Confirm output**

Expected: tests green, no syntax errors, existing CLI unchanged.
