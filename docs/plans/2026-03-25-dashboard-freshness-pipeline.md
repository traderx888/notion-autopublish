# Dashboard Freshness Pipeline Implementation Plan

**Goal:** Move the Market Breadth cards from manual static HTML into a repeatable GitHub Actions refresh pipeline owned by `notion-autopublish`, with explicit per-source freshness states and a canonical normalized artifact.

**Scope:** This rollout only automates the `Market Breadth` section in `output/dashboard.html`. Other dashboard sections remain manually curated, and the page copy must say that clearly.

## Files

- Add: `.github/workflows/dashboard-refresh.yml`
- Add: `tools/refresh_smm_snapshot.py`
- Add: `tools/refresh_dashboard_sources.py`
- Add: `tools/build_dashboard.py`
- Add: `browser/scrapers/aastocks.py`
- Add: `scrape_aastocks.py`
- Add: `docs/plans/2026-03-25-dashboard-freshness-pipeline.md`
- Modify: `tools/dashboard_freshness.py`
- Generate: `scraped_data/smm/latest.json`
- Generate: `scraped_data/hk_breadth/latest.json`
- Generate: `scraped_data/dashboard/refresh_status.json`
- Generate: `scraped_data/dashboard/market_breadth_latest.json`
- Regenerate: `output/dashboard.html`

## Execution

### 1. Normalize source adapters

- Keep SMM normalization in `tools/dashboard_freshness.py` and expose a fetch entrypoint in `tools/refresh_smm_snapshot.py`.
- Reuse the existing `scraped_data/deepvue/market_overview.json` contract and call the existing `scrape_deepvue.py --headless --dashboard market_overview` command from the dashboard refresh orchestration layer.
- Add an AASTOCKS scraper under `browser/scrapers/aastocks.py` plus `scrape_aastocks.py` to persist `scraped_data/hk_breadth/latest.json`.

### 2. Track refresh state

- Persist refresh attempt metadata in `scraped_data/dashboard/refresh_status.json`.
- On success, write the latest attempt time and clear previous errors.
- On failure, keep the previous good artifact, record the latest error, and let the builder render the card as `error` or `stale`.

### 3. Rebuild the dashboard

- Use `tools/build_dashboard.py` to read the three source artifacts, build `scraped_data/dashboard/market_breadth_latest.json`, and replace the `<!-- MARKET BREADTH -->` block in `output/dashboard.html`.
- Rewrite the dashboard subtitle, timestamp, footer, and page title so the page no longer implies whole-dashboard freshness.
- Mirror the rebuilt HTML into `scraped_data/dashboard.html` for local parity.

### 4. Automate in GitHub Actions

- Add `.github/workflows/dashboard-refresh.yml`.
- Run on the Windows self-hosted runner at `09:10 HKT`, `15:35 HKT`, and `16:20 HKT` weekdays, plus `workflow_dispatch`.
- Install dependencies, refresh source artifacts, rebuild the dashboard, run targeted tests, and commit only tracked dashboard artifacts back to `main`.

## Downstream Impact

- `fundman-jarvis` is not receiving a schema change in this rollout.
- The new canonical artifact is `scraped_data/dashboard/market_breadth_latest.json`.
- Downstream consumers should treat the `sources.{source}.status` field as one of `fresh`, `stale`, or `error`.

## Verification Commands

- `python -m pytest tests/test_dashboard_freshness.py -q`
- `python tools/refresh_smm_snapshot.py`
- `python scrape_aastocks.py --headless`
- `python tools/refresh_dashboard_sources.py`
- `python tools/build_dashboard.py`
- `git diff -- output/dashboard.html scraped_data/dashboard/market_breadth_latest.json scraped_data/dashboard/refresh_status.json scraped_data/smm/latest.json scraped_data/hk_breadth/latest.json`
- `python tools/build_dashboard.py`

## Expected Outcome

- The live dashboard derives the SMM, DeepVue, and HK breadth card dates from committed source artifacts.
- A missed source refresh no longer leaves a silently stale card looking fresh.
- GitHub Pages deployment stays on the existing `pages.yml` push flow; the new workflow only refreshes and commits tracked artifacts.
