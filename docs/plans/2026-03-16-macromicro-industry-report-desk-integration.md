# MacroMicro Industry Report Desk Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured MacroMicro industry report detail scraping and feed the resulting research snapshot into `fundman-jarvis` so Market Research Desk and Fundamental / Theme Analyst can consume it directly.

**Architecture:** Extend the existing MacroMicro scraper to follow accessible `industry-report` detail URLs, extract concise structured report fields, and persist a dedicated research snapshot artifact. Then add a lightweight bridge in `fundman-jarvis` to read that artifact, summarize it, and expose it through `market_data` plus newsletter/research helpers.

**Tech Stack:** Playwright persistent session scraper, deterministic DOM parsing, JSON artifacts, pytest.

---

### Task 1: Lock report detail parsing behavior with tests

**Files:**
- Modify: `tests/test_macromicro_scraper.py`

**Step 1: Write failing tests**
- Add a test for normalizing a report detail payload into `title / date / sector / report_type / key_points / questions / answers_preview`.
- Add a test proving `industry-report-list` can follow its accessible detail URLs into a `report_details` collection.

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/test_macromicro_scraper.py -k "industry_report_detail or report_details" -q`

**Step 3: Implement minimal parser**
- Add normalization helpers and any needed extraction helpers in `browser/scrapers/macromicro.py`.

**Step 4: Run tests to verify they pass**
- Run the same focused pytest command.

### Task 2: Add live scraper support for report detail follow-up

**Files:**
- Modify: `browser/scrapers/macromicro.py`
- Modify: `config/macromicro_targets.json`

**Step 1: Write failing tests**
- Add tests proving the scraper follows top accessible report detail URLs for `industry-report-list`.
- Add tests for capped follow count and empty-detail fallback.

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/test_macromicro_scraper.py -k "follow_industry_report or report_detail" -q`

**Step 3: Implement minimal code**
- Add a report-detail extraction path and attach `report_details` plus a compact `research_snapshot` to the list payload.

**Step 4: Run tests to verify they pass**
- Run the same focused pytest command.

### Task 3: Bridge MacroMicro research into fundman-jarvis

**Files:**
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/external_scrapers.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/newsletter_generator.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/agents/market_research.py`
- Modify: `C:/Users/User/Documents/GitHub/fundman-jarvis/agents/fundamental_analyst.py`
- Test: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_macromicro_external_scrapers.py`
- Test: `C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_fundamental_analyst.py`

**Step 1: Write failing tests**
- Add tests for reading the MacroMicro research snapshot from cache and building a compact summary.
- Add desk tests proving Market Research / Fundamental Analyst can surface MacroMicro industry themes in commentary or warnings.

**Step 2: Run tests to verify they fail**
- Run: `pytest C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_macromicro_external_scrapers.py C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_fundamental_analyst.py -q`

**Step 3: Implement minimal code**
- Add cache reader + summarizer helpers in `external_scrapers.py`.
- Inject MacroMicro research into newsletter data collection and desk commentary logic.

**Step 4: Run tests to verify they pass**
- Run the same focused pytest command.

### Task 4: End-to-end verification

**Files:**
- Verify only

**Step 1: Run scraper verification**
- Run: `python scrape_macromicro.py --headless --target industry-report-list`

**Step 2: Run repo tests**
- Run: `pytest tests/test_macromicro_scraper.py -q`
- Run: `pytest C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_macromicro_external_scrapers.py C:/Users/User/Documents/GitHub/fundman-jarvis/tests/test_fundamental_analyst.py -q`

**Step 3: Run syntax verification**
- Run: `python -m py_compile browser/scrapers/macromicro.py scrape_macromicro.py`
- Run: `python -m py_compile C:/Users/User/Documents/GitHub/fundman-jarvis/external_scrapers.py C:/Users/User/Documents/GitHub/fundman-jarvis/newsletter_generator.py C:/Users/User/Documents/GitHub/fundman-jarvis/agents/market_research.py C:/Users/User/Documents/GitHub/fundman-jarvis/agents/fundamental_analyst.py`
