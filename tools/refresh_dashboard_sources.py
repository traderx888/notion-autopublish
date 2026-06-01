from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.dashboard_freshness import REPO_ROOT, SCRAPED_DATA_DIR, now_hkt_iso, read_json, write_json
from tools.refresh_smm_snapshot import refresh_smm_snapshot


REFRESH_STATUS_PATH = SCRAPED_DATA_DIR / "dashboard" / "refresh_status.json"
DEEPVUE_ARTIFACT = SCRAPED_DATA_DIR / "deepvue" / "market_overview.json"
DEEPVUE_PREOPEN_ARTIFACT = SCRAPED_DATA_DIR / "deepvue" / "preopen.json"
HK_ARTIFACT = SCRAPED_DATA_DIR / "hk_breadth" / "latest.json"
SMM_ARTIFACT = SCRAPED_DATA_DIR / "smm" / "latest.json"


def _truncate(message: str, limit: int = 400) -> str:
    text = " ".join(message.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _update_source_status(
    status: dict[str, Any],
    source_key: str,
    *,
    ok: bool,
    last_attempt_at: str,
    artifact_path: Path | None = None,
    error: str | None = None,
    command: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "ok": ok,
        "lastAttemptAt": last_attempt_at,
    }
    if artifact_path is not None:
        entry["artifactPath"] = str(artifact_path.relative_to(REPO_ROOT))
    if command:
        entry["command"] = command
    if error:
        entry["error"] = error
    status.setdefault("sources", {})[source_key] = entry


def _refresh_deepvue_dashboard(
    status: dict[str, Any],
    *,
    source_key: str,
    dashboard: str,
    artifact: Path,
) -> None:
    started_at = now_hkt_iso()
    command = [sys.executable, "scrape_deepvue.py", "--headless", "--dashboard", dashboard]
    result = _run_command(command, REPO_ROOT)
    if result.returncode != 0:
        error = _truncate(result.stderr or result.stdout or f"DeepVue {dashboard} refresh failed without output.")
        _update_source_status(
            status,
            source_key,
            ok=False,
            last_attempt_at=started_at,
            artifact_path=artifact,
            error=error,
            command=" ".join(command),
        )
        return
    if not artifact.exists():
        _update_source_status(
            status,
            source_key,
            ok=False,
            last_attempt_at=started_at,
            artifact_path=artifact,
            error=f"DeepVue command completed but {artifact.relative_to(REPO_ROOT)} was not written.",
            command=" ".join(command),
        )
        return
    _update_source_status(
        status,
        source_key,
        ok=True,
        last_attempt_at=started_at,
        artifact_path=artifact,
        command=" ".join(command),
    )


def _refresh_deepvue(status: dict[str, Any]) -> None:
    # Capture both DeepVue dashboards daily so the consumer (Telegram/CIO) always
    # has same-HKT-day artifacts for market_overview AND preopen.
    _refresh_deepvue_dashboard(
        status,
        source_key="deepvue",
        dashboard="market_overview",
        artifact=DEEPVUE_ARTIFACT,
    )
    _refresh_deepvue_dashboard(
        status,
        source_key="deepvuePreopen",
        dashboard="preopen",
        artifact=DEEPVUE_PREOPEN_ARTIFACT,
    )


def _refresh_hk(status: dict[str, Any]) -> None:
    started_at = now_hkt_iso()
    command = [sys.executable, "scrape_aastocks.py", "--headless"]
    result = _run_command(command, REPO_ROOT)
    if result.returncode != 0:
        error = _truncate(result.stderr or result.stdout or "AASTOCKS refresh failed without output.")
        _update_source_status(
            status,
            "hkBreadth",
            ok=False,
            last_attempt_at=started_at,
            artifact_path=HK_ARTIFACT,
            error=error,
            command=" ".join(command),
        )
        return
    if not HK_ARTIFACT.exists():
        _update_source_status(
            status,
            "hkBreadth",
            ok=False,
            last_attempt_at=started_at,
            artifact_path=HK_ARTIFACT,
            error="AASTOCKS command completed but scraped_data/hk_breadth/latest.json was not written.",
            command=" ".join(command),
        )
        return
    _update_source_status(
        status,
        "hkBreadth",
        ok=True,
        last_attempt_at=started_at,
        artifact_path=HK_ARTIFACT,
        command=" ".join(command),
    )


def refresh_all_sources() -> dict[str, Any]:
    status: dict[str, Any] = {
        "generatedAt": now_hkt_iso(),
        "sources": {},
    }

    smm_started_at = now_hkt_iso()
    try:
        refresh_smm_snapshot(output_path=SMM_ARTIFACT)
    except Exception as exc:
        _update_source_status(
            status,
            "smm",
            ok=False,
            last_attempt_at=smm_started_at,
            artifact_path=SMM_ARTIFACT,
            error=_truncate(str(exc)),
            command=f"{sys.executable} tools/refresh_smm_snapshot.py",
        )
    else:
        _update_source_status(
            status,
            "smm",
            ok=True,
            last_attempt_at=smm_started_at,
            artifact_path=SMM_ARTIFACT,
            command=f"{sys.executable} tools/refresh_smm_snapshot.py",
        )

    _refresh_deepvue(status)
    _refresh_hk(status)
    write_json(REFRESH_STATUS_PATH, status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh all dashboard Market Breadth source artifacts.")
    parser.parse_args()

    status = refresh_all_sources()
    print("Dashboard source refresh summary:")
    for source_key, entry in status.get("sources", {}).items():
        state = "ok" if entry.get("ok") else "error"
        line = f"  - {source_key}: {state}"
        if entry.get("error"):
            line += f" | {entry['error']}"
        print(line)
    print(f"Status artifact: {REFRESH_STATUS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
