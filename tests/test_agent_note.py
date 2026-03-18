import importlib.util
from pathlib import Path


def _load_agent_note_module(repo_root: Path):
    module_path = repo_root / "tools" / "agent_note.py"
    spec = importlib.util.spec_from_file_location("agent_note", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_agent_note_creates_plan_note_with_expected_sections(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "tools").mkdir(parents=True)
    (repo_root / "docs" / "plans").mkdir(parents=True)
    module = _load_agent_note_module(Path(__file__).resolve().parents[1])

    module.REPO_ROOT = repo_root
    output = module.create_note(
        note_type="plan",
        slug="macro-sync",
        title="Macro Sync",
        note_date="2026-03-16",
    )

    assert output == repo_root / "docs" / "plans" / "2026-03-16-macro-sync.md"
    text = output.read_text(encoding="utf-8")
    assert "# Macro Sync Implementation Plan" in text
    assert "**Goal:**" in text
    assert "**Architecture:**" in text


def test_agent_note_creates_handoff_note_with_expected_sections(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "tools").mkdir(parents=True)
    (repo_root / "docs" / "handoffs").mkdir(parents=True)
    module = _load_agent_note_module(Path(__file__).resolve().parents[1])

    module.REPO_ROOT = repo_root
    output = module.create_note(
        note_type="handoff",
        slug="macro-sync",
        title="Macro Sync",
        note_date="2026-03-16",
    )

    assert output == repo_root / "docs" / "handoffs" / "2026-03-16-macro-sync.md"
    text = output.read_text(encoding="utf-8")
    assert "# Handoff" in text
    assert "## Task" in text
    assert "## Verification" in text
