# External Scrapers Ops Dashboard Implementation Note

## Task

Build a local-only operations dashboard in `notion-autopublish` that mirrors the `fundman-jarvis/external_scrapers.py` source inventory, provides grouped source status, and supports local relogin or run actions without exposing live ops state on the public dashboard.

## Owner

- Agent: Codex
- Date: 2026-04-18
- Repo boundary: `notion-autopublish` implementation with inventory alignment to `fundman-jarvis`

## Implementation Scope

- Add an ops registry and status model for grouped fixed sources and advanced parameterized tools.
- Add a local-only HTTP server plus launcher batch file.
- Add a bridge runner for `fundman-jarvis/external_scrapers.py` actions that remain owned by the sibling repo.
- Add a static pointer in `output/dashboard.html` only.
- Add targeted tests for registry coverage, status normalization, action routing, HTTP payload shape, and the public dashboard pointer.

## Verification Plan

- `python -m pytest tests/test_external_scrapers_ops.py -q`
- `python -m pytest tests/test_external_scrapers_ops_server.py -q`
- `python -m pytest tests/test_dashboard_ops_link.py -q`

## Downstream Contract

- No `fundman-jarvis` artifact schema changes are intended.
- The bridge runner must treat `fundman-jarvis/external_scrapers.py` as the inventory reference and invoke its existing functions without mutating its contracts.
