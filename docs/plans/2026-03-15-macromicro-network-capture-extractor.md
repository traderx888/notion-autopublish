# MacroMicro Network Capture Extractor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic network capture extraction for MacroMicro, starting with `fear-and-greed` and `global-recession-rate`, so the scraper can prefer API payloads over DOM parsing.

**Architecture:** Extend the existing Playwright session scraper to collect matching JSON/XHR responses during page load, normalize those responses into per-target extracted data, and persist both raw network artifacts and structured fields in the target payload. Keep DOM/highcharts/bootstrap parsing as fallback when no network payload is captured.

**Tech Stack:** Python, Playwright persistent browser session, pytest, JSON artifacts.

---

### Task 1: Add failing extractor tests

**Files:**
- Modify: `tests/test_macromicro_scraper.py`

**Step 1: Write the failing test**

Add tests for:
- chart target network parsing for `global-recession-rate`
- cross-country target network parsing for `fear-and-greed`
- capture selection logic preferring matching network payloads over empty fallback

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: FAIL because network extractor functions do not exist yet.

### Task 2: Implement network normalization helpers

**Files:**
- Modify: `browser/scrapers/macromicro.py`
- Test: `tests/test_macromicro_scraper.py`

**Step 1: Write minimal implementation**

Add helpers to:
- classify candidate network responses
- normalize chart JSON into latest rows / series summary
- normalize cross-country JSON into country/value cards

**Step 2: Run targeted tests**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: PASS for new unit tests.

### Task 3: Wire capture into runtime scraper

**Files:**
- Modify: `browser/scrapers/macromicro.py`

**Step 1: Implement runtime collection**

Attach Playwright response listeners before navigation, collect small JSON payloads matching MacroMicro API patterns, and persist them in the target payload.

**Step 2: Prefer network extraction**

For `fear-and-greed` and `global-recession-rate`, use network-derived fields first, then fallback to existing bootstrap/highcharts extraction.

**Step 3: Run targeted tests**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: PASS

### Task 4: Verify runtime compatibility

**Files:**
- Modify: `browser/scrapers/macromicro.py`

**Step 1: Syntax verification**

Run: `python -m py_compile browser/scrapers/macromicro.py`
Expected: PASS

**Step 2: Smoke test entrypoint**

Run: `python .\scrape_macromicro.py --headless --target fear-and-greed --target global-recession-rate`
Expected: Either structured JSON with new network fields, or a clean failure that still preserves fallback behavior.
