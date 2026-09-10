"""Bounded Codex CLI adapter for structured newsletter synthesis."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_TIMEOUT_SECONDS = 600


def _extract_json_object(output: str) -> dict[str, Any] | None:
    """Return the first complete JSON object found in model output."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _timeout_seconds() -> int:
    raw = os.environ.get("CODEX_NEWSLETTER_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = int(raw)
    except ValueError:
        print(
            "  [CODEX ERR] CODEX_NEWSLETTER_TIMEOUT_SECONDS must be an integer",
        )
        return DEFAULT_TIMEOUT_SECONDS
    return max(30, timeout)


def synthesize_json(
    prompt: str,
    *,
    label: str = "newsletter",
    model: str | None = None,
) -> dict[str, Any] | None:
    """Run Codex non-interactively and parse its final message as JSON.

    The model has no writable workspace, does not load the user's config, and
    does not persist a Codex session. Authentication is still read from the
    current Windows user's Codex credential store.
    """
    selected_model = model or os.environ.get("CODEX_NEWSLETTER_MODEL", DEFAULT_MODEL)
    timeout = _timeout_seconds()

    try:
        with tempfile.TemporaryDirectory(prefix="codex-newsletter-") as temp_dir:
            output_path = Path(temp_dir) / "last-message.txt"
            command = [
                "codex",
                "exec",
                "--ignore-user-config",
                "--ignore-rules",
                "--ephemeral",
                "--model",
                selected_model,
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--color",
                "never",
                "--output-last-message",
                str(output_path),
                "-",
            ]
            print(
                f"  [CODEX] Synthesizing {label} with {selected_model} "
                f"({len(prompt)} chars)..."
            )
            result = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                cwd=temp_dir,
                check=False,
            )

            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()[:500]
                print(f"  [CODEX ERR] rc={result.returncode}: {detail}")
                return None

            raw_output = (
                output_path.read_text(encoding="utf-8", errors="replace")
                if output_path.exists()
                else result.stdout
            )
            parsed = _extract_json_object(raw_output.strip())
            if parsed is None:
                print("  [CODEX ERR] No valid JSON object found in final response")
                return None
            return parsed

    except FileNotFoundError:
        print("  [CODEX ERR] 'codex' CLI not found on PATH")
        return None
    except subprocess.TimeoutExpired:
        print(f"  [CODEX ERR] Timeout after {timeout}s")
        return None
    except Exception as exc:
        print(f"  [CODEX ERR] {exc}")
        return None
