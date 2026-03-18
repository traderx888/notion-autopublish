# Agent Contract

## Purpose

This document is the shared operating contract for all coding agents working in
`notion-autopublish`. It exists so Codex, Claude Code, Antigravity, and any
other IDE or agent can follow one visible rule set instead of drifting into
tool-specific behavior.

## Rule Precedence

Within the limits of the platform you are running on, follow this order:

1. Direct user request
2. Platform/system/developer/tool constraints
3. This contract
4. [docs/agent_workflow.md](agent_workflow.md)
5. [docs/agent_handoff_template.md](agent_handoff_template.md)
6. Existing repo docs and plans

## Core Principles

- One visible source of truth: no agent should rely on hidden IDE state as the
  primary workflow contract.
- One owner per file at a time: if two agents need the same file, split the
  task or sequence the work.
- Reviewable changes only: prefer branch-based or worktree-based isolation so
  edits can be diffed and verified.
- Evidence before completion: do not say work is done unless verification has
  been run and recorded.
- Preserve user work: never revert unrelated edits just to make the local tree
  cleaner.

## Repo Scope

This repo owns:
- browser automation and persistent-session scraping
- source-specific collectors and capture entrypoints
- generated upstream artifacts in `scraped_data/`
- source/target configuration under `config/`
- publishing or scraping support scripts

This repo does not own downstream portfolio decisions. If an upstream artifact
change affects `fundman-jarvis`, call that out explicitly in the handoff.

## Collaboration Rules

- Use one branch or worktree per agent-task pair.
- Write a dated implementation note in `docs/plans/` for multi-step work.
- If the task spans both `notion-autopublish` and `fundman-jarvis`, name the
  counterpart repo and consumer in the plan.
- Do not silently change JSON/artifact shape. Record additive vs breaking
  behavior.
- If a live scrape is required, keep the artifact path and timestamp in the
  handoff.

## Suggested Ownership Split

These are defaults, not hard requirements:
- Codex: implementation, integration, tests, verification
- Claude Code: research, audit, requirements shaping, narrative synthesis
- Antigravity: alternate implementation spikes, UI/interaction experiments,
  specialized flows

The actual owner must still be explicit in the task plan or handoff.

## Verification Standard

At minimum, before handoff or completion:
- run targeted tests for the touched area
- run syntax/compile checks where relevant
- if scraper behavior changed, refresh either a fixture or a live artifact when
  safe
- record the exact commands and whether they passed

## Required Handoff Contents

Every non-trivial handoff must include:
- what changed
- what remains open
- which files are now authoritative
- verification commands and outcomes
- known risks, stale data, or environment dependencies
