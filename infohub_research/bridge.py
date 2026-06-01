"""Subprocess wrapper around the Info Hub CLI.

Mirrors the discovery + invocation pattern fundman-jarvis uses to call
notion-autopublish scrapers (``external_scrapers.py``):

  1. Find the Info Hub install via env var → sibling → hardcoded fallback.
  2. Locate ``.venv/Scripts/python.exe`` inside that install.
  3. Invoke ``python -m app.cli ...`` with ``PYTHONIOENCODING=utf-8`` set
     in the subprocess env (Windows cp950 will otherwise crash on the
     CLI's mixed-language output).
  4. Capture stdout, parse as JSON, raise on non-zero exit.

We deliberately do NOT import any Info Hub Python — that would require us
to share its venv. The CLI is the contract.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_DEFAULT_FALLBACK = Path(r"C:\Users\User\Documents\Info Hub")


class InfoHubError(RuntimeError):
    """Raised when the Info Hub CLI exits non-zero or returns unparsable output."""

    def __init__(self, message: str, *, command: list[str] | None = None,
                 stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.command = command or []
        self.stdout = stdout
        self.stderr = stderr


@dataclass
class _Discovery:
    root: Path
    python: Path


def _discover_infohub(explicit: str | os.PathLike | None = None) -> _Discovery:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_dir = os.environ.get("INFOHUB_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    # Sibling layout: notion-autopublish and Info Hub share a parent dir.
    here = Path(__file__).resolve().parent.parent
    candidates.append(here.parent / "Info Hub")
    candidates.append(_DEFAULT_FALLBACK)

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            root = candidate.expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if root in seen:
            continue
        seen.add(root)
        if not root.is_dir():
            continue
        python = root / ".venv" / "Scripts" / "python.exe"
        if not python.exists():
            # Allow POSIX layout too, for completeness.
            python_posix = root / ".venv" / "bin" / "python"
            if python_posix.exists():
                python = python_posix
            else:
                continue
        return _Discovery(root=root, python=python)

    raise InfoHubError(
        "Could not locate an Info Hub install with .venv. "
        f"Tried: {', '.join(str(c) for c in candidates)}. "
        "Set INFOHUB_DIR or pass --infohub-dir."
    )


class InfoHubClient:
    """Thin sync wrapper around the Info Hub CLI."""

    def __init__(
        self,
        *,
        infohub_dir: str | os.PathLike | None = None,
        default_timeout: float = 30.0,
        crawl_timeout: float = 300.0,
    ) -> None:
        discovery = _discover_infohub(infohub_dir)
        self.root: Path = discovery.root
        self.python: Path = discovery.python
        self.default_timeout = default_timeout
        self.crawl_timeout = crawl_timeout

    # ── internals ────────────────────────────────────────────────

    def _run(self, args: list[str], *, timeout: float | None = None) -> Any:
        cmd = [str(self.python), "-m", "app.cli", *args]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.root),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.default_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise InfoHubError(
                f"Info Hub CLI timed out after {timeout or self.default_timeout}s: "
                f"{shlex.join(args)}",
                command=cmd,
            ) from exc
        if proc.returncode != 0:
            raise InfoHubError(
                f"Info Hub CLI exited {proc.returncode}: {shlex.join(args)}",
                command=cmd,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        stdout = (proc.stdout or "").strip()
        if not stdout:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise InfoHubError(
                f"Info Hub CLI returned non-JSON output: {exc}",
                command=cmd,
                stdout=proc.stdout,
                stderr=proc.stderr,
            ) from exc

    # ── public CLI surface ───────────────────────────────────────

    def health_check(self) -> bool:
        """Returns True if the CLI is reachable and the registry can be read."""
        try:
            result = self._run(["sources", "list"])
        except InfoHubError:
            return False
        return isinstance(result, list)

    def activate_profile(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Create or merge a watch profile.

        ``spec`` is a flat dict with the same keys as the
        ``infohub watch-profiles activate`` flags.
        """
        args = ["watch-profiles", "activate"]
        for flag, key in (
            ("--name", "name"),
            ("--domain", "domain"),
            ("--theme", "theme"),
            ("--focus", "focus"),
            ("--queries", "queries"),
            ("--negative-terms", "negative_terms"),
            ("--providers", "providers"),
            ("--sources", "sources"),
            ("--notes", "notes"),
        ):
            value = spec.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple)):
                value = ",".join(str(v) for v in value)
            args.extend([flag, str(value)])
        priority = spec.get("priority")
        if priority is not None:
            args.extend(["--priority", str(int(priority))])

        result = self._run(args)
        if not isinstance(result, dict):
            raise InfoHubError(f"activate-profile returned {type(result).__name__}")
        return result

    def crawl_run(
        self,
        source: str,
        keywords: list[str],
        *,
        days: int = 3,
        max_items: int = 5,
    ) -> dict[str, Any]:
        args = [
            "crawl", "run",
            "--source", source,
            "--keywords", ",".join(keywords),
            "--days", str(int(days)),
            "--max-items", str(int(max_items)),
        ]
        result = self._run(args, timeout=self.crawl_timeout)
        if not isinstance(result, dict):
            raise InfoHubError(f"crawl run returned {type(result).__name__}")
        return result

    def items_latest(self, source: str, *, limit: int = 10) -> list[dict[str, Any]]:
        args = ["items", "latest", "--source", source, "--limit", str(int(limit))]
        result = self._run(args)
        if result is None:
            return []
        if not isinstance(result, list):
            raise InfoHubError(f"items latest returned {type(result).__name__}")
        return result
