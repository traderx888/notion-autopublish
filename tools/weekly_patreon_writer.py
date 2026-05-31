"""
Weekly Patreon writer — local file scanner for C:\\blp\\data and friends.

Scans a directory tree for files modified in a date window and emits a
Markdown bundle that 小流 (chief-of-staff) consumes alongside the Notion
side of the weekly pull. The Notion side runs via the Notion MCP search +
fetch tools inside Claude Code; this tool covers the local-files half.

Usage:
    python tools/weekly_patreon_writer.py \\
        --root "C:\\blp\\data" \\
        --since 2026-05-25 \\
        --until 2026-06-01 \\
        --out outputs/weekly/2026-W22-blp-bundle.md

Behavior:
    - Walks --root recursively. Skips hidden dirs and the usual noise
      (.git, __pycache__, node_modules, .venv).
    - Includes files with mtime in [since, until). Default window =
      last 7 days ending today.
    - Emits one markdown section per file with relative path, mtime, size,
      and (for text-ish files under a size cap) the head of the file body.
    - Designed to be idempotent and safe to re-run.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".idea", ".vscode"}
TEXT_EXTS = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".log", ".py",
    ".ipynb", ".html", ".xml", ".tsv", ".rst", ".cfg", ".ini",
}
HEAD_BYTES = 4000
MAX_FILES = 500


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan a dir tree for files in a date window and emit a markdown bundle.")
    p.add_argument("--root", required=True, help="Directory to scan (e.g. C:\\blp\\data).")
    p.add_argument("--since", help="Inclusive start date (YYYY-MM-DD). Default: 7 days ago.")
    p.add_argument("--until", help="Exclusive end date (YYYY-MM-DD). Default: tomorrow.")
    p.add_argument("--out", required=True, help="Output markdown path.")
    p.add_argument("--max-files", type=int, default=MAX_FILES, help=f"Cap on files included (default {MAX_FILES}).")
    p.add_argument("--head-bytes", type=int, default=HEAD_BYTES, help=f"Max bytes of file head to embed (default {HEAD_BYTES}).")
    return p.parse_args(argv)


def _parse_date(s: str | None, default: datetime) -> datetime:
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def collect_files(
    root: Path,
    since: datetime,
    until: datetime,
    *,
    max_files: int = MAX_FILES,
) -> list[dict]:
    """Walk `root` and return [{path, rel, mtime, size}] for files whose mtime
    falls in [since, until). Truncates at max_files (newest first)."""
    hits: list[dict] = []
    if not root.exists():
        return hits
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            full = Path(dirpath) / name
            try:
                stat = full.stat()
            except OSError:
                continue
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            if mtime < since or mtime >= until:
                continue
            hits.append({
                "path": full,
                "rel": str(full.relative_to(root)),
                "mtime": mtime,
                "size": stat.st_size,
            })
    hits.sort(key=lambda h: h["mtime"], reverse=True)
    return hits[:max_files]


def _read_head(path: Path, n: int) -> str:
    try:
        with path.open("rb") as f:
            raw = f.read(n)
    except OSError as e:
        return f"<read error: {e}>"
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def render_bundle(
    root: Path,
    since: datetime,
    until: datetime,
    hits: list[dict],
    *,
    head_bytes: int = HEAD_BYTES,
) -> str:
    lines = [
        f"# Local-files bundle — {root}",
        "",
        f"- Window: {since.date()} → {until.date()}  (exclusive end)",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Files in window: {len(hits)}",
        "",
        "---",
        "",
    ]
    for h in hits:
        size_kb = h["size"] / 1024
        lines.append(f"## `{h['rel']}`")
        lines.append("")
        lines.append(f"- mtime: {h['mtime'].strftime('%Y-%m-%dT%H:%M:%SZ')}")
        lines.append(f"- size: {size_kb:.1f} KB")
        if h["path"].suffix.lower() in TEXT_EXTS and h["size"] <= head_bytes * 4:
            head = _read_head(h["path"], head_bytes)
            lines.append("")
            lines.append("```")
            lines.append(head.rstrip())
            lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = _parse_date(args.since, now - timedelta(days=7))
    until = _parse_date(args.until, now + timedelta(days=1))
    root = Path(args.root)

    if not root.exists():
        print(f"WARN: root does not exist: {root}", file=sys.stderr)

    hits = collect_files(root, since, until, max_files=args.max_files)
    bundle = render_bundle(root, since, until, hits, head_bytes=args.head_bytes)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(bundle, encoding="utf-8")
    print(f"Wrote {len(hits)} entries → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
