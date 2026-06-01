from __future__ import annotations

"""Thin routing bridge for notion-autopublish.

V1 keeps the authoritative routing registry in `jarvis-alerting`. This wrapper
exists only to preserve the existing consumer entrypoint while parity is
verified. Do not grow this back into a repo-local routing authority.
"""

import sys
from pathlib import Path
from typing import Any


def _load_jarvis_alerting():
    try:
        import jarvis_alerting

        return jarvis_alerting
    except ImportError:
        candidate = Path(__file__).resolve().parents[2] / "jarvis-alerts" / "src"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        try:
            import jarvis_alerting

            return jarvis_alerting
        except ImportError:
            return None


def get_active_destinations(alert_key: str, *, config_path: Path | None = None) -> list[dict[str, Any]]:
    runtime = _load_jarvis_alerting()
    if runtime is None:
        return []
    config = runtime.config.load_routing_config(config_path)
    return runtime.config.resolve_destinations(alert_key, config)


def main(argv: list[str] | None = None) -> int:
    runtime = _load_jarvis_alerting()
    if runtime is None:
        raise SystemExit("jarvis_alerting is not available. Install jarvis-alerts or place the peer repo beside notion-autopublish.")
    return runtime.cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
