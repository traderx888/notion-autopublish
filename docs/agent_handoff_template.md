# Agent Handoff Template

Use this template whenever work is handed from one agent or IDE to another.

```md
# Handoff

## Task
- One-sentence description of the task.

## Owner
- Current agent/IDE:
- Branch or worktree:
- Date:

## Scope
- Files changed:
- Files intentionally not touched:
- Repo-local or cross-repo:

## What Changed
- High-signal summary of completed work.
- New files, contracts, or artifacts created.

## Verification
- Commands run:
  - `...`
  - `...`
- Result:
  - passed / failed / partial

## Current State
- What is working now:
- What is still open:
- Any manual steps still required:

## Risks / Notes
- Schema changes:
- Environment or credential dependencies:
- Known edge cases:

## Next Recommended Step
- The most sensible next action for the receiving agent.
```

## Minimum Standard

Do not hand off with only "done" or "almost done". The receiving agent should
be able to continue without reverse-engineering your intent from diffs alone.

