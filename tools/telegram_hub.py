from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

DEFAULT_ROOT = Path(r"C:\Users\User\Documents\GitHub")
DEFAULT_PARSE_MODE = "HTML"
DEFAULT_TASK_NAME = "TelegramHubHourly"
CONTROL_REPO_NAME = "All-in-one"
CONTROL_TASKS_REL_PATH = Path("workflow") / "cross_repo_tasks.yaml"
ALLOWED_DIRS = ("data", "artifacts", "outputs", "reports", "scraped_data")
ALLOWED_SUFFIXES = {".json", ".md", ".txt", ".csv"}
SKIP_FILE_KEYWORDS = (
    "hybrid_memory",
    "jarvis_runs",
    "reminder_log",
    "telegram_alert_log",
    "wdm",
    "listener",
    "offset",
    "inbox",
    "daily_package",
)
INCLUDE_FILE_KEYWORDS = (
    "headline",
    "news",
    "alert",
    "digest",
    "summary",
    "story",
    "signal",
    "market",
)
NOISE_SNIPPETS = {
    "",
    "empty content",
    "unable to parse content",
    "json content",
    "json object",
}
TIMESTAMP_ONLY_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[t ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?(?:z|[+-]\d{2}:\d{2})?$",
    re.IGNORECASE,
)
EN_DATE_ONLY_RE = re.compile(
    r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}$",
    re.IGNORECASE,
)


def _load_structured_config(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        return {}
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _load_cross_repo_tasks(root: Path) -> dict[str, Any]:
    config_path = root / CONTROL_REPO_NAME / CONTROL_TASKS_REL_PATH
    payload = _load_structured_config(config_path)
    tasks = payload.get("tasks")
    return tasks if isinstance(tasks, dict) else {}


def resolve_task_runtime_settings(
    *,
    root: Path,
    task_name: str,
    default_hours: int,
) -> tuple[bool, int]:
    enabled = True
    lookback_hours = max(1, int(default_hours))
    tasks = _load_cross_repo_tasks(root)
    task = tasks.get(task_name)
    if not isinstance(task, dict):
        return enabled, lookback_hours

    raw_enabled = task.get("enabled")
    if isinstance(raw_enabled, bool):
        enabled = raw_enabled
    elif isinstance(raw_enabled, str):
        enabled = raw_enabled.strip().lower() not in {"0", "false", "off", "no", "disabled"}

    raw_hours = task.get("lookback_hours")
    try:
        parsed_hours = int(raw_hours)
        if parsed_hours > 0:
            lookback_hours = parsed_hours
    except Exception:
        pass

    return enabled, lookback_hours


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        return {}
    return out


def load_telegram_credentials(
    *,
    env: dict[str, str] | None = None,
    env_file: Path | None = None,
    fallback_files: list[Path] | None = None,
) -> tuple[str, str]:
    env_map = dict(os.environ if env is None else env)
    token = env_map.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = env_map.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        return token, chat_id

    candidates: list[Path] = []
    shared = env_map.get("TELEGRAM_SHARED_ENV_FILE", "").strip()
    if env_file:
        candidates.append(Path(env_file))
    if shared:
        candidates.append(Path(shared))
    if fallback_files is None:
        candidates.extend(
            [
                DEFAULT_ROOT / ".telegram.env",
                DEFAULT_ROOT / "fundman-jarvis" / ".env",
                Path.cwd() / ".env",
            ]
        )
    else:
        candidates.extend(Path(p) for p in fallback_files)

    seen: set[Path] = set()
    for candidate in candidates:
        path = candidate.resolve() if candidate.exists() else candidate
        if path in seen:
            continue
        seen.add(path)
        values = _read_env_file(candidate)
        if not token:
            token = values.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not chat_id:
            chat_id = values.get("TELEGRAM_CHAT_ID", "").strip()
        if token and chat_id:
            return token, chat_id

    raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")


def _compact_text(text: str, *, max_chars: int = 220) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars] if len(cleaned) > max_chars else cleaned


def _is_noise_file(path_like: str) -> bool:
    lower = (path_like or "").lower()
    return any(token in lower for token in SKIP_FILE_KEYWORDS)


def _is_candidate_file(path_like: str) -> bool:
    lower = (path_like or "").lower()
    return any(token in lower for token in INCLUDE_FILE_KEYWORDS)


def _is_meaningful_snippet(text: str) -> bool:
    value = _compact_text(text)
    lower = value.lower()
    if lower in NOISE_SNIPPETS:
        return False
    if lower.startswith("list items:"):
        return False
    if TIMESTAMP_ONLY_RE.match(lower):
        return False
    if EN_DATE_ONLY_RE.match(lower):
        return False
    if not re.search(r"[a-zA-Z\u4e00-\u9fff]", value):
        return False
    return True


def _snippet_from_json(value: Any) -> str:
    if isinstance(value, dict):
        for key in (
            "summary",
            "headline",
            "title",
            "message",
            "telegram_message",
            "text",
        ):
            v = value.get(key)
            if isinstance(v, (str, int, float, bool)) and str(v).strip():
                return _compact_text(str(v))
        for v in value.values():
            if isinstance(v, (str, int, float, bool)) and str(v).strip():
                candidate = _compact_text(str(v))
                if _is_meaningful_snippet(candidate):
                    return candidate
        return ""
    if isinstance(value, list):
        for item in value[:5]:
            candidate = _snippet_from_json(item)
            if _is_meaningful_snippet(candidate):
                return candidate
        return ""
    if isinstance(value, (str, int, float, bool)):
        candidate = _compact_text(str(value))
        return candidate if _is_meaningful_snippet(candidate) else ""
    return ""


def _extract_snippet(path: Path) -> str:
    try:
        if path.suffix.lower() == ".json":
            text = path.read_text(encoding="utf-8", errors="ignore")
            return _snippet_from_json(json.loads(text))
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            compact = _compact_text(line)
            if _is_meaningful_snippet(compact):
                return compact
    except Exception:
        return "unable to parse content"
    return "empty content"


def _collect_files_for_repo(
    repo: Path,
    *,
    cutoff: datetime,
    max_files_per_repo: int,
) -> list[dict[str, str]]:
    rows: list[tuple[float, Path]] = []
    cutoff_ts = cutoff.timestamp()
    for rel in ALLOWED_DIRS:
        base = repo / rel
        if not base.exists() or not base.is_dir():
            continue
        for file in base.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            try:
                mtime = file.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff_ts:
                continue
            rows.append((mtime, file))

    rows.sort(key=lambda row: row[0], reverse=True)
    out: list[dict[str, str]] = []
    for mtime, file in rows[:max_files_per_repo]:
        rel = file.relative_to(repo).as_posix()
        if _is_noise_file(rel):
            continue
        if not _is_candidate_file(rel):
            continue
        snippet = _extract_snippet(file)
        if not _is_meaningful_snippet(snippet):
            continue
        updated = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        out.append(
            {
                "file": rel,
                "updated_at": updated,
                "snippet": snippet,
            }
        )
        if len(out) >= max_files_per_repo:
            break
    return out


def collect_repo_updates(
    *,
    root: Path,
    hours: int,
    max_files_per_repo: int = 3,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    snapshots: list[dict[str, Any]] = []
    for repo in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        files = _collect_files_for_repo(repo, cutoff=cutoff, max_files_per_repo=max_files_per_repo)
        snapshots.append({"repo": repo.name, "files": files})
    return snapshots


def split_message(text: str, max_length: int) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        piece = line if not current else f"\n{line}"
        if len(current) + len(piece) <= max_length:
            current += piece
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(line) <= max_length:
            current = line
            continue
        # Fallback for very long single lines.
        start = 0
        while start < len(line):
            part = line[start : start + max_length]
            chunks.append(part)
            start += max_length
    if current:
        chunks.append(current)
    return chunks


def _fmt_hkt(iso_utc: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Asia/Hong_Kong")).strftime("%m-%d %H:%M")
    except Exception:
        return "--:--"


def build_digest_messages(
    *,
    snapshots: list[dict[str, Any]],
    hours: int,
    generated_at: datetime,
    max_length: int = 3900,
) -> list[str]:
    active: list[dict[str, Any]] = []
    for row in snapshots:
        usable = []
        for item in row.get("files", []):
            path_like = str(item.get("file", ""))
            snippet = str(item.get("snippet", ""))
            if _is_noise_file(path_like):
                continue
            if not _is_meaningful_snippet(snippet):
                continue
            usable.append(item)
        if usable:
            active.append({"repo": row.get("repo"), "files": usable})

    header = [
        "<b>跨倉庫 Telegram 彙總</b>",
        f"時間窗：過去 {hours} 小時",
        f"生成時間：{generated_at.astimezone(ZoneInfo('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M HKT')}",
        "",
    ]

    if not active:
        return ["\n".join(header + ["本時段沒有可發送的跨倉庫內容。"]).strip()]

    lines = list(header)
    for snap in active:
        repo_name = html.escape(str(snap["repo"]))
        lines.append(f"<b>【{repo_name}】</b>")
        for item in snap.get("files", []):
            snippet = html.escape(str(item.get("snippet", "")))
            stamp = _fmt_hkt(str(item.get("updated_at", "")))
            lines.append(f"• ({stamp}) {snippet or 'no snippet'}")
        lines.append("")

    return split_message("\n".join(lines).strip(), max_length=max_length)


def send_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = DEFAULT_PARSE_MODE,
    session=requests,
    timeout: int = 20,
) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    resp = session.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok", False):
        raise RuntimeError(f"Telegram API error: {data}")


def send_messages(
    *,
    bot_token: str,
    chat_id: str,
    messages: list[str],
    parse_mode: str = DEFAULT_PARSE_MODE,
) -> None:
    for msg in messages:
        send_message(bot_token=bot_token, chat_id=chat_id, text=msg, parse_mode=parse_mode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate updates from all local repos and send to Telegram")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Root folder containing repos")
    parser.add_argument("--hours", type=int, default=8, help="Lookback window in hours")
    parser.add_argument("--task-name", type=str, default=DEFAULT_TASK_NAME, help="Task name key for control config")
    parser.add_argument("--max-files-per-repo", type=int, default=3, help="Max files shown per repo")
    parser.add_argument("--max-length", type=int, default=3900, help="Max Telegram message length")
    parser.add_argument("--env-file", type=Path, default=None, help="Explicit env file containing Telegram creds")
    parser.add_argument("--send", action="store_true", help="Actually send Telegram messages")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task_name = (args.task_name or DEFAULT_TASK_NAME).strip() or DEFAULT_TASK_NAME
    task_enabled, runtime_hours = resolve_task_runtime_settings(
        root=args.root,
        task_name=task_name,
        default_hours=args.hours,
    )
    if not task_enabled:
        print(f"Telegram delivery: skipped ({task_name} disabled by {CONTROL_REPO_NAME}/workflow/cross_repo_tasks.yaml)")
        return 0

    snapshots = collect_repo_updates(
        root=args.root,
        hours=runtime_hours,
        max_files_per_repo=args.max_files_per_repo,
    )
    messages = build_digest_messages(
        snapshots=snapshots,
        hours=runtime_hours,
        generated_at=datetime.now(timezone.utc),
        max_length=args.max_length,
    )

    active_count = sum(1 for row in snapshots if row.get("files"))
    print(f"Scanned repos: {len(snapshots)}")
    print(f"Repos with updates: {active_count}")
    print(f"Generated messages: {len(messages)}")

    if args.send:
        token, chat_id = load_telegram_credentials(env_file=args.env_file)
        if "本時段沒有可發送的跨倉庫內容" in messages[0]:
            print("Telegram delivery: skipped (no meaningful content)")
        else:
            send_messages(bot_token=token, chat_id=chat_id, messages=messages)
            print("Telegram delivery: sent")
    else:
        print("Telegram delivery: skipped (--send not set)")
        print("=" * 56)
        print(messages[0])
        print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
