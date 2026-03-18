from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip()).strip("-").lower()
    return text or "agent-note"


def _titleize_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("-", " ").split()) or "Agent Note"


def _render_plan(title: str) -> str:
    return (
        f"# {title} Implementation Plan\n\n"
        "> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.\n\n"
        f"**Goal:** Define the goal for {title}.\n\n"
        f"**Architecture:** Describe the approach for {title}.\n\n"
        "**Tech Stack:** Document the key tools, libraries, or services.\n\n"
        "---\n"
    )


def _render_handoff() -> str:
    return (
        "# Handoff\n\n"
        "## Task\n"
        "- One-sentence description of the task.\n\n"
        "## Owner\n"
        "- Current agent/IDE:\n"
        "- Branch or worktree:\n"
        "- Date:\n\n"
        "## Scope\n"
        "- Files changed:\n"
        "- Files intentionally not touched:\n"
        "- Repo-local or cross-repo:\n\n"
        "## What Changed\n"
        "- High-signal summary of completed work.\n\n"
        "## Verification\n"
        "- Commands run:\n"
        "  - `...`\n"
        "- Result:\n"
        "  - passed / failed / partial\n\n"
        "## Current State\n"
        "- What is working now:\n"
        "- What is still open:\n\n"
        "## Risks / Notes\n"
        "- Known dependencies:\n"
        "- Known edge cases:\n\n"
        "## Next Recommended Step\n"
        "- The most sensible next action for the receiving agent.\n"
    )


def create_note(
    *,
    note_type: str,
    slug: str,
    title: str | None = None,
    note_date: str | None = None,
) -> Path:
    normalized_type = (note_type or "").strip().lower()
    if normalized_type not in {"plan", "handoff"}:
        raise ValueError("note_type must be 'plan' or 'handoff'")

    normalized_slug = _slugify(slug)
    rendered_title = (title or "").strip() or _titleize_slug(normalized_slug)
    rendered_date = (note_date or "").strip() or datetime.now().strftime("%Y-%m-%d")

    if normalized_type == "plan":
        output_dir = REPO_ROOT / "docs" / "plans"
        content = _render_plan(rendered_title)
    else:
        output_dir = REPO_ROOT / "docs" / "handoffs"
        content = _render_handoff()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{rendered_date}-{normalized_slug}.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an agent plan or handoff note.")
    parser.add_argument("note_type", choices=["plan", "handoff"])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title")
    parser.add_argument("--date", dest="note_date")
    args = parser.parse_args()

    output = create_note(
        note_type=args.note_type,
        slug=args.slug,
        title=args.title,
        note_date=args.note_date,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
