# Handoffs Directory

This directory stores working handoff notes passed between agents or IDEs.

## Naming Rule

Use:

```text
YYYY-MM-DD-<slug>.md
```

Examples:
- `2026-03-16-macromicro-refresh.md`
- `2026-03-16-p-model-runtime-cleanup.md`

If the same topic needs multiple same-day handoffs, add a short suffix:
- `2026-03-16-macromicro-refresh-v2.md`
- `2026-03-16-macromicro-refresh-codex-to-claude.md`

## How To Create One

Use the helper command:

```powershell
python .\tools\agent_note.py handoff --slug macromicro-refresh --title "MacroMicro Refresh"
```

Or copy the structure from:
- [docs/agent_handoff_template.md](../agent_handoff_template.md)

## What Must Be In A Handoff

- task
- owner
- branch or worktree
- files changed
- verification commands
- current state
- next recommended step

## Retention Rule

- active or unresolved handoffs: keep
- completed same-repo handoffs: keep for 30 days
- completed cross-repo handoffs or operational incidents: keep for 90 days

After the retention window:
- keep the durable decision in a canonical doc or plan if it still matters
- then delete the handoff note

## What Not To Store Here

- permanent architecture docs
- final runbooks
- long research writeups

Those belong in `docs/`, `docs/plans/`, or another canonical location.

