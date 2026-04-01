# jarvis-alerts V1 Pilot Note

**Date:** 2026-03-31
**Owner:** Codex

## Goal

Shift alert routing and delivery ownership out of `notion-autopublish` and into the new peer repo `jarvis-alerts`, while keeping repo-specific digest and audit assembly local.

## Scope

- Keep `tools/telegram_hub.py` responsible for digest assembly only.
- Route delivery via `jarvis_alerting.emit`.
- Reduce `tools/alert_router.py` to a package wrapper around `jarvis-alerting`.
- Add a non-breaking publish workflow pilot that activates once the remote `jarvis-alerts` repo and token are available.
- Pin the workflow checkout to a tested `jarvis-alerts` commit SHA instead of tracking a moving branch.

## Authoritative Interfaces

- `tools/telegram_hub.py::send_to_destinations()` is the delivery bridge.
- `tools/alert_router.py` is no longer the routing source of truth.
- `jarvis-alerts/src/jarvis_alerting/data/alert_routing.json` is the intended routing registry for the pilot.
- `.github/workflows/publish.yml` is the authoritative GitHub Actions integration point for publish result alerts.

## Guardrails

- Keep `telegram_hub.py` and `alert_router.py` as thin consumer bridges only.
- Use consumer overrides only for route-level behavior such as test-chat wiring or temporary enable/disable.
- Do not move repo-scan, digest, or schedule-audit ownership into `jarvis-alerts` during V1.
- Keep the workflow dependency pinned to `016bf23510b657c2bc9625fd57b010881d58fde4` until the next deliberate upgrade.

## Verification

- `python -m pytest -q tools\test_telegram_hub.py tools\test_jarvis_alerting_bridge.py tools\test_alert_router_wrapper.py`
- `Select-String -Path .github\workflows\publish.yml -Pattern 'JARVIS_ALERTS_REF|traderx888/jarvis-alerts|016bf23510b657c2bc9625fd57b010881d58fde4'`
- Dry-run smoke on branch `2026-03-31-publish-dry-run-smoke`:
  - run `23830503308` confirmed `Checkout jarvis-alerts` succeeded
  - run `23830503308` also confirmed `publish.py --dry-run` could query the `Content Calendar` database using `NOTION_DATABASE_ID=5c6b531d-a701-4543-8be5-6366b12f26ca`
