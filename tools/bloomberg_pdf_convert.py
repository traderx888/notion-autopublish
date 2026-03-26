"""Bloomberg PDF → Markdown converter.

Scans C:\\blp\\data\\ for new PDFs, extracts text via pypdf,
strips Bloomberg disclaimers, parses topic hashtags from filenames,
and writes .md files to C:\\blp\\data\\md_converted\\.

State tracked in outputs/ops/bloomberg_pipeline_state.json.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fix Windows cp950 encoding for CJK filenames in console output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PDF_DIR = Path(r"C:\blp\data")
MD_DIR = PDF_DIR / "md_converted"
STATE_PATH = REPO_ROOT / "outputs" / "ops" / "bloomberg_pipeline_state.json"

HKT = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# Disclaimer / boilerplate patterns to strip
# ---------------------------------------------------------------------------
DISCLAIMER_PATTERNS: list[re.Pattern[str]] = [
    # "This document is being provided for the exclusive use of ..."
    re.compile(
        r"This document is being provided for the exclusive use of .+?\."
        r"[\s]*Not for redistribution\.",
        re.IGNORECASE,
    ),
    # "This report may not be modified or altered ..."
    re.compile(r"This report may not be modi.+?(?=\n\n|\Z)", re.DOTALL),
    # Printed on date lines
    re.compile(r"Printed on \d{2}/\d{2}/\d{4}"),
    # Page N of M
    re.compile(r"Page \d+ of \d+"),
    # Bloomberg copyright footer
    re.compile(
        r"(?:©|\(c\)|Copyright)\s*\d{4}\s*Bloomberg\.?\s*(?:L\.?P\.?|Finance)?"
        r".*?(?:reserved|Bloomberg)",
        re.IGNORECASE | re.DOTALL,
    ),
    # Standalone "Bloomberg" line at the top
    re.compile(r"^Bloomberg\s*$", re.MULTILINE),
    # "News Story" header line
    re.compile(r"^News Story\s*$", re.MULTILINE),
]


def now_hkt_iso() -> str:
    return datetime.now(HKT).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------
def read_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "lastRunAt": None,
        "lastNewsletterNumber": 5,
        "processedFiles": {},
        "newsletters": {},
        "weeklyDigests": {},
    }


def write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Topic parsing from filename hashtags
# ---------------------------------------------------------------------------
def parse_topics(filename: str) -> list[str]:
    """Extract #hashtag topics from a PDF filename."""
    return [t.lower() for t in re.findall(r"#(\w+)", filename)]


def title_from_filename(filename: str) -> str:
    """Derive a clean article title from the PDF filename."""
    name = Path(filename).stem
    # Remove hashtags and surrounding whitespace
    name = re.sub(r"\s*#\w+", "", name).strip()
    # Remove trailing parenthetical duplicates like (1), (2)
    name = re.sub(r"\s*\(\d+\)\s*$", "", name).strip()
    return name


# ---------------------------------------------------------------------------
# PDF text extraction + cleaning
# ---------------------------------------------------------------------------
def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from all pages of a PDF via pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def strip_disclaimers(text: str) -> str:
    """Remove Bloomberg boilerplate / disclaimers from extracted text."""
    for pat in DISCLAIMER_PATTERNS:
        text = pat.sub("", text)
    # Collapse excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Single-file conversion
# ---------------------------------------------------------------------------
def convert_one(pdf_path: Path) -> Path:
    """Convert a single PDF to cleaned markdown. Returns the .md path."""
    raw = extract_pdf_text(pdf_path)
    cleaned = strip_disclaimers(raw)
    title = title_from_filename(pdf_path.name)

    md_name = re.sub(r"[<>:\"/\\|?*]", "", title)[:120] + ".md"
    md_path = MD_DIR / md_name

    # Build markdown content
    topics = parse_topics(pdf_path.name)
    tag_line = " ".join(f"#{t}" for t in topics) if topics else ""
    header = f"# {title}\n"
    if tag_line:
        header += f"\n**Tags:** {tag_line}\n"
    header += f"\n**Source:** Bloomberg  \n**Converted:** {now_hkt_iso()}\n\n---\n\n"

    md_path.write_text(header + cleaned, encoding="utf-8")
    return md_path


# ---------------------------------------------------------------------------
# Batch conversion
# ---------------------------------------------------------------------------
def run(dry_run: bool = False) -> dict:
    """Convert all new PDFs. Returns summary stats."""
    state = read_state()
    processed = state["processedFiles"]

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    new_count = 0
    skipped = 0
    errors: list[str] = []

    for pdf_path in pdf_files:
        fname = pdf_path.name
        if fname in processed:
            skipped += 1
            continue

        if dry_run:
            topics = parse_topics(fname)
            print(f"[DRY-RUN] Would convert: {fname}  topics={topics}")
            new_count += 1
            continue

        try:
            md_path = convert_one(pdf_path)
            topics = parse_topics(fname)
            processed[fname] = {
                "processedAt": now_hkt_iso(),
                "mdPath": str(md_path),
                "topics": topics,
                "newsletterNumber": None,
            }
            new_count += 1
            print(f"[OK] {fname} → {md_path.name}  topics={topics}")
        except Exception as exc:
            errors.append(f"{fname}: {exc}")
            print(f"[ERR] {fname}: {exc}", file=sys.stderr)

    if not dry_run:
        state["lastRunAt"] = now_hkt_iso()
        write_state(state)

    summary = {"new": new_count, "skipped": skipped, "errors": len(errors)}
    print(f"\nDone: {new_count} converted, {skipped} skipped, {len(errors)} errors")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert Bloomberg PDFs to Markdown")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
