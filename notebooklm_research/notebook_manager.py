"""NotebookLM notebook lifecycle manager.

Manages a per-ticker notebook registry and creates/retrieves
notebooks via the notebooklm-py client.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_registry(registry_path: Path) -> dict[str, str]:
    """Load the ticker → notebook_id registry from disk.

    Returns empty dict if file does not exist.
    """
    if not registry_path.exists():
        return {}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_registry(registry: dict[str, str], registry_path: Path) -> None:
    """Persist the ticker → notebook_id registry to disk."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


async def get_or_create_notebook(
    client: Any,
    ticker: str,
    registry: dict[str, str],
    registry_path: Path,
) -> str:
    """Return an existing notebook_id for *ticker*, or create a new one.

    If the registry has an entry but the notebook no longer exists on
    NotebookLM, a new notebook is created and the registry is updated.
    """
    existing_id = registry.get(ticker)

    if existing_id:
        try:
            await client.notebooks.get(existing_id)
            return existing_id
        except Exception:
            # Notebook was deleted — fall through to create
            pass

    notebook = await client.notebooks.create(f"Research: {ticker}")
    notebook_id = notebook.id
    registry[ticker] = notebook_id
    save_registry(registry, registry_path)
    return notebook_id
