# Audit Rules

## Normalization

- `JARVIS-Reminder-<task>` -> `<task>` with hyphens converted to underscores
- `pam_check` -> `p_model_check`
- `Fundman-Storyteller-1030` -> `story_1030`
- `run_deepvue_dashboard.bat` -> `deepvue_dashboard`
- `run_sector_screenshots.bat` -> `sector_heatmap`
- `TelegramHubHourly` -> `telegram_hub_hourly`
- `publish.yml` cron -> `notion_publish_daily`

## Drift Types

- `missing_in_control`: Scheduler-deployed task is not represented in `cross_repo_tasks.yaml`
- `missing_in_scheduler`: Control-enabled task is not currently deployed in Windows Task Scheduler
- `missing_in_repo`: Control or scheduler task has no matching repo-defined source
- `schedule_mismatch`: Control schedule text and scheduler schedule text disagree
- `enabled_mismatch`: Control enabled state and scheduler enabled state disagree
- `orphaned_wrapper`: Wrapper exists in repo but is not represented in control or scheduler
- `info_only_schedule`: Automation schedule exists but is informational rather than Telegram-control drift

## Remediation Order

1. Update repo code or wrapper definitions when the implementation source is missing.
2. Update `All-in-one/workflow/cross_repo_tasks.yaml` when control metadata is missing or stale.
3. Re-register or adjust Windows scheduled tasks only after the first two layers are correct.

## Reporting Rules

- Always emit `Summary`, `Missing In Control`, `Missing In Scheduler`, `Missing In Repo`, `Schedule Mismatches`, `Informational`, and `Checklist`.
- Prefer exact task keys in the checklist so the remediation step is directly actionable.
- Keep GitHub Actions schedules in the informational bucket unless they are explicitly part of Telegram-control drift.
