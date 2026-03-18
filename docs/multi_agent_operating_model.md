# Multi-Agent Operating Model

## Purpose

This document describes how multiple IDE agents should collaborate across
`notion-autopublish` and `fundman-jarvis` without relying on hidden tool state.

## Repo Roles

- `notion-autopublish`
  - upstream scraping
  - browser/session automation
  - publishing support
  - source artifacts and manifests
- `fundman-jarvis`
  - downstream research synthesis
  - policy, portfolio, and alert consumers
  - role-based analyst outputs
  - operator-facing workflows

## Recommended Default Ownership

- Codex
  - implementation
  - integration
  - tests
  - verification
- Claude Code
  - research
  - audits
  - requirements shaping
  - synthesis and writeups
- Antigravity
  - alternative spikes
  - experimentation
  - UI or interaction-oriented work

These are defaults only. Every non-trivial task should still declare one active
owner.

## How To Split Work

Split work when:
- one repo produces an artifact and the other consumes it
- one agent needs a manual browser or credentialed flow
- one part of the work is research-heavy and another is implementation-heavy

Do not split work when:
- two agents would edit the same file
- the handoff overhead is larger than the implementation itself

## Branch / Worktree Model

- one branch or worktree per agent-task pair
- no concurrent edits to the same file
- if several agents are active, use separate worktrees rather than shared local
  state

Suggested branch format:
- `YYYY-MM-DD-topic`

## Shared Contract

Every agent should read:
- `AGENTS.md`
- `docs/agent_contract.md`
- `docs/agent_workflow.md`
- `docs/agent_handoff_template.md`

If an IDE supports its own entry file, keep it as a thin wrapper only.

## Handoff Standard

Use the handoff template for any non-trivial transfer. At minimum include:
- task
- owner
- changed files
- verification commands
- current state
- next recommended step

## Plan / Handoff Generator

This repo includes a small helper:

```powershell
python .\tools\agent_note.py plan --slug macromicro-refresh --title "MacroMicro Refresh"
python .\tools\agent_note.py handoff --slug macromicro-refresh --title "MacroMicro Refresh"
```

Outputs:
- `docs/plans/YYYY-MM-DD-<slug>.md`
- `docs/handoffs/YYYY-MM-DD-<slug>.md`

## Cross-Repo Rule

If a change here affects `fundman-jarvis`, the handoff must identify:
- the artifact path
- the schema or field contract
- freshness or timing assumptions
- the downstream consumer

