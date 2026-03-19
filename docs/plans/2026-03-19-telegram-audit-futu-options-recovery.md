# Telegram Audit Futu/Options Recovery Note

**Owner:** Codex

**Counterpart Repo:** `fundman-jarvis`

**Goal:** Keep the schedule-audit consumer aligned with the restored `fundman-jarvis` Futu/OpenD, Friday volume, and Friday options Telegram wrappers.

**Files:**
- `tools/telegram_schedule_audit.py`
- `tools/test_telegram_schedule_audit.py`

**Shared Artifact Consumed:**
- `C:\Users\User\Documents\GitHub\All-in-one\workflow\cross_repo_tasks.yaml`

**Recovered Task Keys:**
- `friday_volume`
- `futu_signals`
- `friday_options`

**Verification:**
- `python -m pytest tools\test_telegram_schedule_audit.py -q`
- `python tools\telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish --only-issues`
