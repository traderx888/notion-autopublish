from __future__ import annotations

import csv
import json
from pathlib import Path


def write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_history_row(path: str | Path, row: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_header = not target.exists()
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def load_recent_history(path: str | Path, limit: int = 5) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-limit:]

