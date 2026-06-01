# Insider Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add HedgeFollow largest insider buys and largest insider sells coverage to this repo as a scrapeable artifact and surface the latest snapshot inside the checked-in dashboard HTML.

**Architecture:** Create a small public Playwright scraper for HedgeFollow that captures the rendered 1-week insider tables, normalizes the top rows into JSON, and emits a reusable dashboard HTML section snippet. Then splice that new insider section into the existing dashboard artifacts so the dashboard shows both buy-side and sell-side insider flow.

**Tech Stack:** Python, Playwright, JSON artifacts, static HTML, pytest.

---

### Task 1: Lock insider normalization and dashboard rendering with tests

**Files:**
- Create: `tests/test_hedgefollow_insiders.py`

**Step 1: Write failing tests**
- Add a test proving promo/ad rows are filtered and valid HedgeFollow rows normalize into `symbol / company_name / trade_value_text / trade_value_numeric / range_low / range_high / primary_insider / insider_summary / stock_url`.
- Add a test proving artifact writing emits `hedgefollow_insiders_latest.json`, per-side JSON files, and `insider_dashboard_section.html`.
- Add a test proving dashboard section rendering includes both Largest Insider Buys and Largest Insider Sells tables plus source links.

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/test_hedgefollow_insiders.py -q`

**Step 3: Write minimal implementation**
- Implement the pure helper functions in `browser/scrapers/hedgefollow_insiders.py`.

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/test_hedgefollow_insiders.py -q`

### Task 2: Add live HedgeFollow scrape support

**Files:**
- Create: `browser/scrapers/hedgefollow_insiders.py`
- Create: `scrape_hedgefollow_insiders.py`

**Step 1: Write failing tests**
- Extend `tests/test_hedgefollow_insiders.py` with a CLI smoke test if the entrypoint behavior needs coverage.

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/test_hedgefollow_insiders.py -q`

**Step 3: Write minimal implementation**
- Add the public Playwright scraper, live row extraction, manifest generation, and artifact persistence under `scraped_data/hedgefollow_insiders/`.

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/test_hedgefollow_insiders.py -q`

### Task 3: Add insider flow to the dashboard artifacts

**Files:**
- Modify: `output/dashboard.html`
- Modify: `scraped_data/dashboard.html`

**Step 1: Generate fresh insider artifact**
- Run: `python scrape_hedgefollow_insiders.py --headless`

**Step 2: Insert the new section**
- Add a new `Insider Flow` section showing top buy-side and sell-side rows sourced from the latest HedgeFollow snapshot.
- Keep the visual language aligned with the existing dashboard cards and tables.

**Step 3: Verify the section renders cleanly**
- Re-open the dashboard locally or inspect the HTML diff for both dashboard artifacts.

### Task 4: Verification

**Files:**
- Verify only

**Step 1: Focused tests**
- Run: `pytest tests/test_hedgefollow_insiders.py -q`

**Step 2: Syntax checks**
- Run: `python -m py_compile browser/scrapers/hedgefollow_insiders.py scrape_hedgefollow_insiders.py`

**Step 3: Live scrape verification**
- Run: `python scrape_hedgefollow_insiders.py --headless`
- Expected: fresh JSON and HTML artifacts under `scraped_data/hedgefollow_insiders/`

**Step 4: Repo state capture**
- Run: `git status --short`
- Record that the change is additive and local to `notion-autopublish`; no `fundman-jarvis` contract change is expected.
