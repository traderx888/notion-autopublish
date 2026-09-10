# Codex Newsletter Self-Hosted Runner

## Task

Replace Claude-based Bloomberg newsletter synthesis with a bounded Codex CLI
call using `gpt-5.6-sol`, retain the pytest gate and direct `main` publication,
and register a Windows self-hosted runner on this computer.

## Owner and Isolation

- Owner: Codex
- Branch: `codex/2026-09-10-codex-newsletter-runner`
- Worktree: `tmp/worktrees/codex-newsletter-runner`
- Repo-local code change plus host-level GitHub Actions runner installation

## Scope

- Add a reusable, read-only, ephemeral Codex JSON synthesis adapter.
- Switch both newsletter and Sunday digest synthesis away from Claude/Anthropic.
- Pin and verify the Codex CLI in the GitHub Actions workflow.
- Add focused tests for command construction, parsing, and failure behavior.
- Update the operator runbook.
- Register and start a repo-scoped Windows x64 self-hosted runner only after the
  updated workflow reaches `main`.

## Safety Boundaries

- Do not reuse or clean the existing dirty checkout.
- Do not expose GitHub registration tokens or Codex credentials in logs.
- Codex runs with `--ignore-user-config`, `--ephemeral`, and a read-only sandbox.
- Cancel the currently queued old-workflow run before bringing the runner online.
- Stage only owned files, secret-scan the staged diff, verify the private remote,
  and push the reviewed commit to the task branch before the authorized `main`
  update.

## Verification

- Focused unit tests for the Codex adapter and Bloomberg pipeline.
- Python compile checks for touched modules.
- Local minimal `gpt-5.6-sol` probe returning an exact sentinel.
- Workflow YAML parse/read-back.
- GitHub runner registration read-back (`online`, correct labels).
- Fresh manual workflow dispatch from the updated `main`, followed through to
  completion or an evidence-backed blocker.

## Downstream Impact

- Generated newsletter HTML and `outputs/ops/bloomberg_pipeline_state.json`
  retain their existing shape.
- No `fundman-jarvis` schema or consumer change is intended.
