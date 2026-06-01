# Autopublish Deliverables Implementation Plan

**Owner:** Codex
**Branch:** `codex/2026-05-26-autopublish-deliverables`
**Date:** 2026-05-26

## Goal

Add the four requested deliverables for the local review/backtest toolkit:

- `README.md`: system overview and installation steps while preserving existing repo docs.
- `review/30day_review_prompt.md`: copy/paste Codex review prompt.
- `backtest/run_backtest.py`: yfinance-backed thesis backtest framework with optional Notion write-back.
- `docs/ARCHITECTURE.md`: architecture, limitations, and five-phase upgrade path.

Follow-up requested in the same thread: add a local dashboard to monitor generated review/backtest results.

## Scope

Repo-local work only. This change creates a new upstream backtest/review workflow but does not change an existing generated artifact schema consumed by `fundman-jarvis`.

## Approach

1. Preserve existing user-modified files and avoid replacing current README content wholesale.
2. Add tests for the backtest framework before implementation.
3. Create the requested review and architecture docs from the supplied zip content.
4. Implement the backtest module with dependency injection so tests do not require live Notion or yfinance calls.
5. Update dependency documentation and run targeted verification.
6. Add a local dashboard that reads backtest CSV artifacts and `review/review_*.md` reports without requiring live Notion credentials.

## Verification Log

- `pytest tests/test_run_backtest.py -q` before implementation: failed with `ModuleNotFoundError: No module named 'backtest'`, confirming the RED state.
- `python -m pytest tests/test_run_backtest.py::test_short_rule_does_not_match_em_inside_other_words -q` before the EM-rule fix: failed because `EM` matched inside `Semiconductors`.
- `python -m pytest tests/test_run_backtest.py -q`: passed, `6 passed in 0.74s`.
- `python -m py_compile backtest/run_backtest.py`: passed with exit code 0.
- `python backtest/run_backtest.py --help`: passed with exit code 0 and displayed the quarter/start/end/benchmark/output/write-back options.
- `python -c "from pathlib import Path; [Path(p).read_text(encoding='utf-8') for p in ['README.md','review/30day_review_prompt.md','docs/ARCHITECTURE.md','docs/plans/2026-05-26-autopublish-deliverables.md']]; print('utf8-ok')"`: passed, printed `utf8-ok`.
- `pytest tests/test_run_backtest.py -q`: passed, `6 passed in 0.66s`.
- `pytest tests/test_review_backtest_dashboard.py -q` before dashboard implementation: failed with `ModuleNotFoundError: No module named 'tools.build_review_backtest_dashboard'`, confirming the RED state.
- `pytest tests/test_review_backtest_dashboard.py -q`: passed, `2 passed in 0.13s`.
- `python tools/build_review_backtest_dashboard.py`: passed, generated `output/review_backtest_dashboard.html` and `outputs/backtest/review_backtest_dashboard_latest.json`; current local artifacts contain `Backtest rows: 0` and `Review reports: 0`.
- Browser verification via local static server at `http://127.0.0.1:8766/output/review_backtest_dashboard.html`: page title and H1 were `Review / Backtest Monitor`; body showed the no-data empty states and runbook commands. The only browser console error was `/favicon.ico` 404 from the temporary static server.
