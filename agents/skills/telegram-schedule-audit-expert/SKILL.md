---
name: telegram-schedule-audit-expert
description: Audit daily Telegram schedules and cross-repo task drift across All-in-one, fundman-jarvis, and notion-autopublish. Use when checking whether Windows scheduled tasks, repo-defined reminder jobs, and control-file task entries are missing, mismatched, disabled, or out of sync, and when producing a Telegram-ready audit report plus remediation checklist.
---

# Telegram Schedule Audit Expert

Use this skill to inspect the three operational truths for the Telegram schedule stack:

1. Windows Task Scheduler deployment state
2. Repo-defined task sources in `fundman-jarvis` and `notion-autopublish`
3. Cross-repo control state in `All-in-one/workflow/cross_repo_tasks.yaml`

## Workflow

1. Run `python tools/telegram_schedule_audit.py --root C:\Users\User\Documents\GitHub --repos All-in-one fundman-jarvis notion-autopublish --only-issues` from `notion-autopublish`.
2. Read the generated JSON artifact at `outputs/ops/telegram_schedule_audit_latest.json`.
3. If the user wants delivery, re-run with `--send`.
4. When drift is found, update source-of-truth files before touching Windows Task Scheduler.
5. Only use scheduler registration scripts after the source files are aligned.

## Scope Rules

- Treat `All-in-one/workflow/cross_repo_tasks.yaml` as the control layer for enablement and ownership metadata.
- Treat `fundman-jarvis/daily_reminders.py` plus wrapper `.bat` files as the repo layer for Telegram runtime tasks.
- Treat `notion-autopublish/tools/run_telegram_hub.bat` and `.github/workflows/publish.yml` as the repo layer for cross-repo digest and publishing automation.
- Do not auto-fix drift unless the user asks for it explicitly.

## References

- Read `references/audit-rules.md` for normalization rules, issue semantics, and remediation order.
