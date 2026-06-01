"""Export curated research notes as Fundman-Jarvis memory capsules.

This is an upstream artifact generator. It intentionally accepts only curated
summaries, not raw full chat transcripts. The downstream fundman-jarvis bridge
performs stricter validation and dedupe before Hermes ingestion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = REPO_ROOT / "scraped_data" / "jarvis_memory" / "inbox"
DEFAULT_OUTPUT = REPO_ROOT / "scraped_data" / "jarvis_memory" / "memory_capsules_latest.jsonl"

_SECRET_PATTERNS = [
    re.compile(
        r"(?i)\b(DISCORD_BOT_TOKEN|TELEGRAM_BOT_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY|NOTION_TOKEN|"
        r"SUPABASE_KEY|SUPABASE_SERVICE_ROLE_KEY|GITHUB_TOKEN|HERMES_TOKEN)\s*=\s*([^\s,;]+)"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bntn_[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{24,}\b"),
]


def redact_text(value: Any) -> str:
    text = "" if value is None else str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


def _as_list(value: Any, *, uppercase: bool = False) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(part).strip() for part in value]
    else:
        return []
    cleaned = [redact_text(item).strip() for item in items if redact_text(item).strip()]
    if uppercase:
        cleaned = [item.upper() for item in cleaned]
    return list(dict.fromkeys(cleaned))


def _normalize_evidence(value: Any, source_path: Path) -> list[Any]:
    if isinstance(value, list) and value:
        return _redact_nested(value)
    if isinstance(value, str) and value.strip():
        return [redact_text(value).strip()]
    return [{"title": source_path.name, "path": str(source_path)}]


def _redact_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_nested(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _derive_id(record: dict[str, Any]) -> str:
    source = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(record.get("source_tool") or "curated")).strip("-").lower()
    seed = "|".join(
        [
            str(record.get("source_tool") or ""),
            str(record.get("topic") or ""),
            str(record.get("summary") or ""),
            str(record.get("created_at") or ""),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"{source or 'curated'}:{digest}"


def _normalize_record(raw: dict[str, Any], source_path: Path) -> dict[str, Any] | None:
    topic = redact_text(raw.get("topic") or raw.get("title") or source_path.stem).strip()
    summary = redact_text(raw.get("summary") or raw.get("content") or raw.get("notes") or "").strip()
    if not topic or not summary:
        return None

    record = {
        "id": redact_text(raw.get("id") or "").strip(),
        "created_at": redact_text(raw.get("created_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")).strip(),
        "source_tool": redact_text(raw.get("source_tool") or raw.get("source") or "notion-autopublish").strip(),
        "topic": topic,
        "tickers": _as_list(raw.get("tickers"), uppercase=True),
        "summary": summary,
        "evidence": _normalize_evidence(raw.get("evidence"), source_path),
        "decision_impact": redact_text(raw.get("decision_impact") or "").strip(),
        "confidence": raw.get("confidence", 0.5),
        "expires_at": redact_text(raw.get("expires_at") or "").strip(),
        "notion_page_id": redact_text(raw.get("notion_page_id") or "").strip(),
        "artifact_paths": _as_list(raw.get("artifact_paths") or str(source_path)),
    }
    if not record["id"]:
        record["id"] = _derive_id(record)
    return _redact_nested(record)


def _load_json_file(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _load_jsonl_file(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _load_markdown_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = path.stem
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("#").strip() or title
    body = "\n".join(line for line in lines if not line.startswith("---")).strip()
    if not body:
        return []
    return [
        {
            "source_tool": "curated-markdown",
            "topic": title,
            "summary": body[:4000],
            "evidence": [{"title": path.name, "path": str(path)}],
            "artifact_paths": [str(path)],
        }
    ]


def _load_records(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    if path.is_file():
        candidates = [path]
    elif path.is_dir():
        candidates = sorted(
            p for p in path.rglob("*") if p.suffix.lower() in {".json", ".jsonl", ".md"}
        )
    else:
        return []

    records: list[tuple[Path, dict[str, Any]]] = []
    for item_path in candidates:
        suffix = item_path.suffix.lower()
        if suffix == ".json":
            raw_records = _load_json_file(item_path)
        elif suffix == ".jsonl":
            raw_records = _load_jsonl_file(item_path)
        elif suffix == ".md":
            raw_records = _load_markdown_file(item_path)
        else:
            raw_records = []
        records.extend((item_path, raw) for raw in raw_records)
    return records


def export_memory_capsules(input_path: str | Path, output_path: str | Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    source = Path(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    accepted = []
    skipped = []
    for source_path, raw in _load_records(source):
        normalized = _normalize_record(raw, source_path)
        if normalized is None:
            skipped.append({"file": str(source_path), "reason": "missing topic or summary"})
            continue
        accepted.append(normalized)

    accepted = sorted(accepted, key=lambda item: item["id"])
    output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in accepted),
        encoding="utf-8",
    )

    report = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_path": str(source),
        "output_path": str(output),
        "accepted_count": len(accepted),
        "skipped_count": len(skipped),
        "accepted_ids": [item["id"] for item in accepted],
        "skipped": skipped,
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export curated research notes as Jarvis memory capsules.")
    parser.add_argument("--input", default=str(DEFAULT_INBOX), help="Curated JSON/JSONL/Markdown inbox.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSONL artifact.")
    parser.add_argument("--json", action="store_true", help="Print the export report as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = export_memory_capsules(args.input, args.output)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "Jarvis memory capsules exported: "
            f"accepted={report['accepted_count']} skipped={report['skipped_count']} output={report['output_path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
