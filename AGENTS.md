# Agent Instructions

This repository is used by multiple coding agents and IDEs. Do not assume any
hidden IDE rule set is shared across tools. The canonical collaboration rules
for this repo live in:

1. [docs/agent_contract.md](docs/agent_contract.md)
2. [docs/agent_workflow.md](docs/agent_workflow.md)
3. [docs/agent_handoff_template.md](docs/agent_handoff_template.md)
4. [docs/multi_agent_operating_model.md](docs/multi_agent_operating_model.md)

If an IDE supports its own local rule file, that file must mirror these docs
instead of inventing a separate workflow.

## Repo Mission

`notion-autopublish` owns content publishing, browser automation, source
scraping, and upstream structured artifacts consumed by downstream systems such
as `fundman-jarvis`.

Typical high-impact areas:
- `browser/` for Playwright/session-backed scrapers
- `scrape_*.py` entrypoints
- `config/` target registries and source configuration
- `scraped_data/` generated artifacts and manifests
- `docs/plans/` implementation plans and rollout notes

## Mandatory Working Rules

- Use a dedicated branch or worktree per agent-task pair.
- Treat `docs/agent_contract.md` as the shared source of truth across Codex,
  Claude Code, Antigravity, and any other agent.
- For multi-step work, create or update a dated plan under `docs/plans/`.
- Do not let two agents edit the same file concurrently.
- If a schema or artifact contract changes, document the downstream impact,
  especially for `fundman-jarvis`.
- Before claiming completion, run targeted verification and record the commands
  plus the actual result.

## Cross-Repo Boundary

If a change here affects `fundman-jarvis`, hand off with:
- the artifact path
- the schema or field change
- the intended downstream consumer
- the verification command that proves the upstream artifact is valid
