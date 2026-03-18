# MacroMicro Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a browser-session MacroMicro scraper that captures configured chart and cross-country targets into JSON, screenshots, and a latest manifest, then expose it through the existing CLI and `fundman-jarvis` wrapper.

**Architecture:** Build a new `MacroMicroScraper` on top of `BrowserAutomation`, using persistent Playwright session plus optional manual login. Parse page data from inline scripts and rendered Highcharts objects instead of direct HTTP calls because MacroMicro is Cloudflare-protected and raw requests return 403 or incomplete payloads. Keep outputs additive under `scraped_data/macromicro/` and mirror the established DeepVue wrapper pattern in `fundman-jarvis`.

**Tech Stack:** Python, Playwright sync API, pytest, JSON artifacts, browser persistent sessions

---

### Task 1: Contract And Fixtures

**Files:**
- Create: `tests/test_macromicro_scraper.py`
- Create: `docs/plans/2026-03-15-macromicro-scraper.md`

**Step 1: Write the failing tests**

Cover:
- default targets include the two currently referenced MacroMicro URLs
- chart inline-script parsing extracts metadata and last rows
- Highcharts extraction normalizes timestamps and series points
- cross-country inline-script parsing extracts title and area definitions
- bundle writer emits per-target JSON plus `macromicro_latest.json`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: FAIL because `browser.scrapers.macromicro` does not exist yet.

### Task 2: Scraper Core

**Files:**
- Create: `browser/scrapers/macromicro.py`
- Modify: `browser/scrapers/__init__.py`

**Step 1: Write minimal implementation**

Implement:
- target registry with default chart and cross-country targets
- helper functions for target normalization and output naming
- deterministic parsers for chart inline scripts, Highcharts series, and cross-country inline scripts
- `MacroMicroScraper` with session check, manual login prompt, page capture, screenshot, JSON write, and bundle manifest write

**Step 2: Run targeted tests**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: PASS for parsing/manifest tests.

### Task 3: CLI Entry Points

**Files:**
- Modify: `browser/cli.py`
- Create: `scrape_macromicro.py`

**Step 1: Write the failing test**

Extend `tests/test_macromicro_scraper.py` with CLI-level resolution checks:
- `browser scrape macromicro`
- `scrape_macromicro.py --target sentiment-combinations`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: FAIL because CLI options are missing.

**Step 3: Write minimal implementation**

Add:
- `macromicro` service to browser CLI
- standalone `scrape_macromicro.py` entry point
- target selection and `--headless`, `--target`, `--url` flags

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_macromicro_scraper.py -q`
Expected: PASS.

### Task 4: Fundman Wrapper

**Files:**
- Modify: `c:\Users\User\Documents\GitHub\fundman-jarvis\external_scrapers.py`
- Create: `c:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_macromicro_external_scrapers.py`

**Step 1: Write the failing test**

Cover:
- wrapper invokes `scrape_macromicro.py`
- cached reader returns latest manifest payload
- required-file readiness includes `scrape_macromicro.py`

**Step 2: Run test to verify it fails**

Run: `pytest c:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_macromicro_external_scrapers.py -q`
Expected: FAIL because wrapper and constants are missing.

**Step 3: Write minimal implementation**

Add:
- MacroMicro output constants
- `scrape_macromicro()` subprocess wrapper
- `get_macromicro_cached()` manifest reader

**Step 4: Run test to verify it passes**

Run: `pytest c:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_macromicro_external_scrapers.py -q`
Expected: PASS.

### Task 5: Verification

**Files:**
- Modify: none

**Step 1:** Run `pytest tests/test_macromicro_scraper.py -q`

**Step 2:** Run `pytest c:\Users\User\Documents\GitHub\fundman-jarvis\tests\test_macromicro_external_scrapers.py -q`

**Step 3:** Run `python -m py_compile browser/scrapers/macromicro.py scrape_macromicro.py browser/cli.py c:\Users\User\Documents\GitHub\fundman-jarvis\external_scrapers.py`

**Step 4:** If a local session already exists, optionally run `python scrape_macromicro.py --target global-recession-rate --headless` and inspect `scraped_data/macromicro/macromicro_latest.json`.
