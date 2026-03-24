# Signal-Triggered Fundamental Research via NotebookLM

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When DeepVue or SMM Golden EP flags a sector or stock, programmatically push relevant YouTube sources (earnings calls, analyst videos) into a per-ticker NotebookLM notebook, query NotebookLM for fundamental changes, and save the result as a human-readable `.md` file that the fundamental desk and CIO can consume.

**Architecture:** Mirrors the existing `ciovacco/notebooklm_sync.py` pattern — a new `fundamental_research/` module in `notion-autopublish` handles notebook lifecycle, deduplication, and structured Q&A. Output is `.md` with YAML frontmatter (machine-parseable metadata + human-readable prose answers). `fundman-jarvis` reads the output files as plain text, the same way it reads Substack `.txt` files. Auth remains external via `notebooklm login` cookie session.

**Two execution paths (design for both):**
- **Batch/scheduled path** — Python CLI `scrape_fundamental_research.py` called with a ticker + YouTube URL list; saves `.md` to `scraped_data/notebooklm/`
- **Interactive path** — `notebooklm-skill-master` MCP skill lets Claude Code query NLM notebooks directly mid-conversation for ad-hoc analyst requests (no code needed for this; it uses the existing skill)

**Tech Stack:** Python 3.11/3.12, `notebooklm-py`, `pytest`, `python-frontmatter`, existing `ciovacco` pattern as reference.

**Output format rationale:** `.md` over `.json` because:
- NLM answers are prose — a fundamental analyst reads them directly
- YAML frontmatter gives machine-parseable metadata for fundman-jarvis routing
- Consistent with how Substack `.txt` files work (human-readable prose) but adds structure via headers
- fundman-jarvis ingests it the same way as `capitalwars_latest.txt` — pass as text to Claude for extraction

---

### Task 1: Define the output contract in tests

**Files:**
- Create: `tests/test_fundamental_notebooklm.py`
- No production files yet

**Context:** The Ciovacco sync already exists at `ciovacco/notebooklm_sync.py` — read it before writing tests. This new module is a generalisation of that pattern to any ticker.

**Step 1: Write failing tests for config resolution**

```python
# tests/test_fundamental_notebooklm.py
import pytest
from fundamental_research.notebooklm_research import (
    resolve_research_config,
    build_fundamental_questions,
    render_research_markdown,
    find_source_by_url,
)


def test_resolve_config_from_explicit_args():
    cfg = resolve_research_config(
        notebook_id="nb-abc123",
        storage_path="/tmp/auth.json",
        env={},
    )
    assert cfg["notebook_id"] == "nb-abc123"
    assert cfg["storage_path"] == "/tmp/auth.json"


def test_resolve_config_from_env():
    cfg = resolve_research_config(
        notebook_id=None,
        storage_path=None,
        env={"FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID_NVDA": "nb-nvda-xyz"},
        ticker="NVDA",
    )
    assert cfg["notebook_id"] == "nb-nvda-xyz"


def test_resolve_config_missing_notebook_id_raises():
    with pytest.raises(ValueError, match="notebook ID"):
        resolve_research_config(notebook_id=None, storage_path=None, env={}, ticker="AAPL")
```

**Step 2: Run to verify failure**

```bash
cd c:\Users\User\Documents\GitHub\notion-autopublish
pytest tests/test_fundamental_notebooklm.py -q
```
Expected: `ImportError: No module named 'fundamental_research'`

**Step 3: Write failing tests for question building**

```python
def test_build_fundamental_questions_returns_four_keys():
    signal = {
        "ticker": "NVDA",
        "sector": "semiconductors",
        "trigger_source": "SMM_GOLDEN_EP",
        "trigger_signal": "sector_breakout",
        "youtube_urls": ["https://www.youtube.com/watch?v=abc123"],
    }
    questions = build_fundamental_questions(signal)
    assert set(questions.keys()) == {"earnings_change", "management_tone", "thesis_validity", "key_risks"}
    # Each question must mention the ticker
    for key, q in questions.items():
        assert "NVDA" in q, f"Question '{key}' does not mention ticker"


def test_build_fundamental_questions_sector_in_context():
    signal = {"ticker": "TSM", "sector": "foundry", "trigger_source": "DEEPVUE",
              "trigger_signal": "breakout", "youtube_urls": []}
    questions = build_fundamental_questions(signal)
    assert "foundry" in questions["thesis_validity"].lower() or "TSM" in questions["thesis_validity"]
```

**Step 4: Write failing tests for MD rendering**

```python
def test_render_research_markdown_has_frontmatter():
    signal = {
        "ticker": "NVDA", "sector": "semiconductors",
        "trigger_source": "SMM_GOLDEN_EP", "trigger_signal": "sector_breakout",
        "youtube_urls": ["https://www.youtube.com/watch?v=abc123"],
    }
    answers = {
        "earnings_change": {"question": "Q1", "answer": "Revenue beat by 8%.", "conversation_id": "c1"},
        "management_tone": {"question": "Q2", "answer": "Bullish on data centre.", "conversation_id": "c1"},
        "thesis_validity": {"question": "Q3", "answer": "Intact.", "conversation_id": "c1"},
        "key_risks": {"question": "Q4", "answer": "Export restrictions.", "conversation_id": "c1"},
    }
    md = render_research_markdown(
        signal=signal,
        answers=answers,
        notebook_id="nb-nvda",
        notebook_title="FundamentalResearch_NVDA",
        synced_at="2026-03-24T10:00:00+00:00",
    )
    assert md.startswith("---"), "Must start with YAML frontmatter"
    assert "ticker: NVDA" in md
    assert "trigger_source: SMM_GOLDEN_EP" in md
    assert "## Earnings Change" in md
    assert "Revenue beat by 8%" in md
    assert "## Key Risks" in md


def test_render_research_markdown_youtube_urls_in_frontmatter():
    signal = {
        "ticker": "AAPL", "sector": "consumer_tech",
        "trigger_source": "MANUAL", "trigger_signal": "ad_hoc",
        "youtube_urls": ["https://www.youtube.com/watch?v=xyz"],
    }
    md = render_research_markdown(
        signal=signal, answers={}, notebook_id="nb-aapl",
        notebook_title="FundamentalResearch_AAPL",
        synced_at="2026-03-24T10:00:00+00:00",
    )
    assert "youtube_urls:" in md
    assert "watch?v=xyz" in md
```

**Step 5: Write failing test for URL deduplication helper**

```python
def test_find_source_by_url_canonical_match():
    # Reuse the same helper pattern from ciovacco/notebooklm_sync.py
    from fundamental_research.notebooklm_research import find_source_by_url

    class FakeSource:
        def __init__(self, url):
            self.url = url

    sources = [FakeSource("https://www.youtube.com/watch?v=abc123")]
    # youtu.be short URL should match canonical
    match = find_source_by_url(sources, "https://youtu.be/abc123")
    assert match is not None

    no_match = find_source_by_url(sources, "https://youtu.be/zzz999")
    assert no_match is None
```

**Step 6: Run all to confirm they all fail on ImportError**

```bash
pytest tests/test_fundamental_notebooklm.py -q
```
Expected: `ImportError: No module named 'fundamental_research'`

---

### Task 2: Implement `fundamental_research/notebooklm_research.py`

**Files:**
- Create: `fundamental_research/__init__.py` (empty)
- Create: `fundamental_research/notebooklm_research.py`

**Context:** Read `ciovacco/notebooklm_sync.py` before implementing — reuse `canonicalize_source_url` and `find_source_by_url` logic exactly (do not copy-paste; import from `ciovacco.notebooklm_sync` or duplicate minimally). The key difference: this module is ticker-parameterised and outputs `.md`, not a dict.

**Step 1: Create the module skeleton**

```python
# fundamental_research/__init__.py
# (empty)
```

```python
# fundamental_research/notebooklm_research.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable

from notebooklm import NotebookLMClient

# Re-use URL helpers from ciovacco module (don't duplicate)
from ciovacco.notebooklm_sync import canonicalize_source_url, find_source_by_url


_SECTION_TITLES = {
    "earnings_change": "Earnings Change",
    "management_tone": "Management Tone",
    "thesis_validity": "Thesis Validity",
    "key_risks": "Key Risks",
}

_QUESTION_ORDER = ["earnings_change", "management_tone", "thesis_validity", "key_risks"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_research_config(
    *,
    notebook_id: str | None = None,
    storage_path: str | None = None,
    env: dict[str, str] | None = None,
    ticker: str | None = None,
) -> dict[str, str | None]:
    env_map = env or {}
    # Ticker-specific env var first, then generic fallback
    ticker_key = f"FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID_{(ticker or '').upper()}"
    resolved_nb = (
        notebook_id
        or env_map.get(ticker_key, "")
        or env_map.get("FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID", "")
    ).strip()
    if not resolved_nb:
        raise ValueError(
            f"Missing NotebookLM notebook ID. Pass --notebook-id or set {ticker_key}."
        )
    resolved_storage = (
        storage_path
        or env_map.get("NOTEBOOKLM_STORAGE_PATH", "")
        or env_map.get("FUNDAMENTAL_NOTEBOOKLM_STORAGE", "")
    ).strip() or None
    return {"notebook_id": resolved_nb, "storage_path": resolved_storage}


def build_fundamental_questions(signal: dict) -> dict[str, str]:
    ticker = signal.get("ticker", "").upper()
    sector = signal.get("sector", "")
    trigger_signal = signal.get("trigger_signal", "")

    return {
        "earnings_change": (
            f"For {ticker} ({sector}), what changed in the most recently added sources "
            f"versus historical notebook entries? Focus on: earnings beats/misses, revenue/margin guidance "
            f"revisions, and any surprise vs consensus. The trigger signal was: {trigger_signal}. "
            "Use notebook history to quantify the delta, not just describe the current state."
        ),
        "management_tone": (
            f"Analyse the management tone shift for {ticker} across the notebook sources. "
            "Look for: hedging language increases or decreases, capital allocation changes (buybacks, capex), "
            "confidence signals in forward guidance, and any notable changes in how leadership frames risk."
        ),
        "thesis_validity": (
            f"Based on all notebook sources for {ticker} in the {sector} sector, is the current bull thesis "
            f"intact, impaired, or strengthened after the '{trigger_signal}' signal? "
            "State the single strongest supporting evidence and the single biggest threat. "
            "End with: INTACT / IMPAIRED / STRENGTHENED."
        ),
        "key_risks": (
            f"List the actionable risk watchpoints and invalidation levels for {ticker} from the combined "
            "notebook sources. For each risk: (1) what is the catalyst, (2) what price/data level invalidates "
            "the thesis, (3) what timeframe. Rank by probability × impact."
        ),
    }


def render_research_markdown(
    *,
    signal: dict,
    answers: dict[str, dict[str, str]],
    notebook_id: str,
    notebook_title: str,
    synced_at: str,
) -> str:
    ticker = signal.get("ticker", "")
    sector = signal.get("sector", "")
    trigger_source = signal.get("trigger_source", "")
    trigger_signal = signal.get("trigger_signal", "")
    youtube_urls = signal.get("youtube_urls", [])

    url_lines = "\n".join(f"  - {u}" for u in youtube_urls) if youtube_urls else "  []"

    frontmatter = (
        "---\n"
        f"ticker: {ticker}\n"
        f"sector: {sector}\n"
        f"trigger_source: {trigger_source}\n"
        f"trigger_signal: {trigger_signal}\n"
        f"notebook_id: {notebook_id}\n"
        f"notebook_title: {notebook_title}\n"
        f"synced_at: {synced_at}\n"
        f"youtube_urls:\n{url_lines}\n"
        "---\n"
    )

    body_parts = [f"# Fundamental Research: {ticker}\n"]
    body_parts.append(f"**Sector:** {sector}  \n**Triggered by:** {trigger_source} — {trigger_signal}  \n**Synced:** {synced_at}\n")

    for key in _QUESTION_ORDER:
        if key not in answers:
            continue
        title = _SECTION_TITLES.get(key, key.replace("_", " ").title())
        answer_text = answers[key].get("answer", "")
        body_parts.append(f"\n## {title}\n\n{answer_text}\n")

    return frontmatter + "\n".join(body_parts)


async def _default_client_factory(storage_path: str | None):
    return await NotebookLMClient.from_storage(path=storage_path)


async def sync_fundamental_research(
    signal: dict,
    *,
    notebook_id: str,
    storage_path: str | None = None,
    client_factory: Callable[[str | None], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """
    Core async function: adds YouTube URLs to a NLM notebook, asks structured
    fundamental questions, and returns a result dict including rendered_md.

    signal keys: ticker, sector, trigger_source, trigger_signal, youtube_urls (list)
    """
    youtube_urls: list[str] = signal.get("youtube_urls", [])
    questions = build_fundamental_questions(signal)
    build_client = client_factory or _default_client_factory
    client = await build_client(storage_path)

    async with client as active_client:
        notebook = await active_client.notebooks.get(notebook_id)
        summary = await active_client.notebooks.get_summary(notebook_id)
        existing_sources = await active_client.sources.list(notebook_id)

        sources_added = []
        for url in youtube_urls:
            source = find_source_by_url(existing_sources, url)
            if source is None:
                source = await active_client.sources.add_url(notebook_id, url, wait=False)
                source = await active_client.sources.wait_until_ready(notebook_id, source.id)
                sources_added.append(url)

        answers: dict[str, dict[str, str]] = {}
        for key, question in questions.items():
            result = await active_client.chat.ask(notebook_id, question)
            answers[key] = {
                "question": question,
                "answer": result.answer,
                "conversation_id": result.conversation_id,
            }

    synced_at = _now_iso()
    rendered_md = render_research_markdown(
        signal=signal,
        answers=answers,
        notebook_id=notebook_id,
        notebook_title=getattr(notebook, "title", ""),
        synced_at=synced_at,
    )

    return {
        "synced_at": synced_at,
        "ticker": signal.get("ticker", ""),
        "notebook_id": notebook_id,
        "notebook_title": getattr(notebook, "title", ""),
        "summary": summary,
        "sources_added": sources_added,
        "answers": answers,
        "rendered_md": rendered_md,
    }
```

**Step 2: Run tests**

```bash
pytest tests/test_fundamental_notebooklm.py -q
```
Expected: PASS on all 7 tests.

**Step 3: Commit**

```bash
git add fundamental_research/ tests/test_fundamental_notebooklm.py
git commit -m "feat: add fundamental_research NotebookLM sync module with MD output"
```

---

### Task 3: CLI entry point `scrape_fundamental_research.py`

**Files:**
- Create: `scrape_fundamental_research.py`
- Modify: `requirements.txt` (add `notebooklm-py[browser]` if not already present)

**Context:** Check `scrape_ciovacco.py` for the CLI pattern. The new script accepts ticker, sector, trigger metadata, and one or more YouTube URLs. It can also accept a `--signal-file` JSON path for automated triggers from DeepVue/SMM in future.

**Step 1: Write failing tests for CLI behaviour**

Add to `tests/test_fundamental_notebooklm.py`:

```python
# Test the signal file loading helper
from scrape_fundamental_research import load_signal_from_file, build_signal_from_args
import json, pathlib, tempfile


def test_load_signal_from_file(tmp_path):
    signal = {
        "ticker": "TSMC",
        "sector": "foundry",
        "trigger_source": "SMM_GOLDEN_EP",
        "trigger_signal": "sector_momentum",
        "youtube_urls": ["https://www.youtube.com/watch?v=test123"],
    }
    f = tmp_path / "signal.json"
    f.write_text(json.dumps(signal), encoding="utf-8")
    loaded = load_signal_from_file(str(f))
    assert loaded["ticker"] == "TSMC"
    assert len(loaded["youtube_urls"]) == 1


def test_build_signal_from_args():
    signal = build_signal_from_args(
        ticker="AMD",
        sector="semiconductors",
        trigger_source="DEEPVUE",
        trigger_signal="momentum_breakout",
        youtube_urls=["https://youtu.be/abc", "https://youtu.be/def"],
    )
    assert signal["ticker"] == "AMD"
    assert len(signal["youtube_urls"]) == 2
    assert "youtube.com/watch" in signal["youtube_urls"][0]  # canonicalized


def test_build_signal_from_args_normalises_ticker():
    signal = build_signal_from_args(
        ticker="nvda", sector="semis", trigger_source="MANUAL",
        trigger_signal="ad_hoc", youtube_urls=[],
    )
    assert signal["ticker"] == "NVDA"
```

**Step 2: Run tests to verify failure**

```bash
pytest tests/test_fundamental_notebooklm.py -q -k "signal"
```
Expected: `ImportError: cannot import name 'load_signal_from_file' from 'scrape_fundamental_research'`

**Step 3: Implement the CLI script**

```python
# scrape_fundamental_research.py
"""
CLI: trigger fundamental research via NotebookLM for a given stock/sector signal.

Usage examples:
  # Manual one-shot:
  python scrape_fundamental_research.py \\
      --ticker NVDA --sector semiconductors \\
      --trigger-source DEEPVUE --trigger-signal momentum_breakout \\
      --notebook-id <NLM_NOTEBOOK_ID> \\
      --youtube https://www.youtube.com/watch?v=abc \\
      --youtube https://www.youtube.com/watch?v=def

  # From a signal JSON file (for automated triggers from SMM/DeepVue):
  python scrape_fundamental_research.py --signal-file path/to/signal.json --notebook-id <ID>

Output: scraped_data/notebooklm/{ticker_lower}_fundamental.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from ciovacco.notebooklm_sync import canonicalize_source_url
from fundamental_research.notebooklm_research import (
    resolve_research_config,
    sync_fundamental_research,
)

OUTPUT_DIR = Path("scraped_data/notebooklm")


def load_signal_from_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["ticker"] = data.get("ticker", "").upper()
    data["youtube_urls"] = [canonicalize_source_url(u) for u in data.get("youtube_urls", [])]
    return data


def build_signal_from_args(
    *,
    ticker: str,
    sector: str,
    trigger_source: str,
    trigger_signal: str,
    youtube_urls: list[str],
) -> dict:
    return {
        "ticker": ticker.upper(),
        "sector": sector,
        "trigger_source": trigger_source,
        "trigger_signal": trigger_signal,
        "youtube_urls": [canonicalize_source_url(u) for u in youtube_urls],
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run fundamental research via NotebookLM")
    p.add_argument("--signal-file", help="Path to JSON signal file (alternative to manual flags)")
    p.add_argument("--ticker", help="Stock ticker, e.g. NVDA")
    p.add_argument("--sector", default="", help="Sector label, e.g. semiconductors")
    p.add_argument("--trigger-source", default="MANUAL", help="e.g. SMM_GOLDEN_EP, DEEPVUE, MANUAL")
    p.add_argument("--trigger-signal", default="ad_hoc", help="Signal description")
    p.add_argument("--youtube", dest="youtube_urls", action="append", default=[],
                   metavar="URL", help="YouTube URL to add (repeat for multiple)")
    p.add_argument("--notebook-id", help="NotebookLM notebook ID (or set FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID_{TICKER})")
    p.add_argument("--notebooklm-storage", help="Path to notebooklm auth storage_state.json")
    return p.parse_args()


async def _main():
    args = _parse_args()

    if args.signal_file:
        signal = load_signal_from_file(args.signal_file)
    elif args.ticker:
        signal = build_signal_from_args(
            ticker=args.ticker,
            sector=args.sector,
            trigger_source=args.trigger_source,
            trigger_signal=args.trigger_signal,
            youtube_urls=args.youtube_urls,
        )
    else:
        print("ERROR: Provide --ticker or --signal-file.", file=sys.stderr)
        sys.exit(1)

    env = dict(os.environ)
    cfg = resolve_research_config(
        notebook_id=args.notebook_id,
        storage_path=args.notebooklm_storage,
        env=env,
        ticker=signal["ticker"],
    )

    print(f"[fundamental-research] Syncing {signal['ticker']} ({signal['sector']}) "
          f"triggered by {signal['trigger_source']}: {signal['trigger_signal']}")
    print(f"[fundamental-research] YouTube sources: {signal['youtube_urls']}")

    result = await sync_fundamental_research(
        signal,
        notebook_id=cfg["notebook_id"],
        storage_path=cfg["storage_path"],
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{signal['ticker'].lower()}_fundamental.md"
    out_path.write_text(result["rendered_md"], encoding="utf-8")
    print(f"[fundamental-research] Saved → {out_path}")

    if result.get("sources_added"):
        print(f"[fundamental-research] New sources added: {result['sources_added']}")
    else:
        print("[fundamental-research] No new sources (all URLs already in notebook)")

    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(_main())
```

**Step 4: Run tests**

```bash
pytest tests/test_fundamental_notebooklm.py -q
```
Expected: PASS on all tests.

**Step 5: Smoke-test compile**

```bash
python -m py_compile scrape_fundamental_research.py fundamental_research/notebooklm_research.py
```
Expected: no output (no syntax errors).

**Step 6: Commit**

```bash
git add scrape_fundamental_research.py tests/test_fundamental_notebooklm.py
git commit -m "feat: add scrape_fundamental_research CLI with signal-file + manual modes"
```

---

### Task 4: Wire output into fundman-jarvis

**Files:**
- Modify: `c:\Users\User\Documents\GitHub\fundman-jarvis\external_scrapers.py`
- Modify: `c:\Users\User\Documents\GitHub\fundman-jarvis\requirements.txt` (add `python-frontmatter` if not present)

**Context:** fundman-jarvis already reads Substack `.txt` files via subprocess. The new `.md` files are even easier — just read and pass. No subprocess needed; just `Path.read_text()`. Check `external_scrapers.py` to find the pattern used for `scrape_capital_wars()` and follow the same convention.

**Step 1: Write failing test in fundman-jarvis**

```python
# tests/test_fundamental_research_reader.py (in fundman-jarvis)
import json
from pathlib import Path
import pytest

from external_scrapers import read_fundamental_research, list_fundamental_research_tickers


FIXTURE_MD = """\
---
ticker: NVDA
sector: semiconductors
trigger_source: SMM_GOLDEN_EP
trigger_signal: sector_breakout
notebook_id: nb-test
notebook_title: FundamentalResearch_NVDA
synced_at: 2026-03-24T10:00:00+00:00
youtube_urls:
  - https://www.youtube.com/watch?v=abc123
---

# Fundamental Research: NVDA

## Earnings Change

Revenue beat by 8%.

## Key Risks

Export restrictions remain the #1 tail risk.
"""


def test_read_fundamental_research(tmp_path):
    (tmp_path / "nvda_fundamental.md").write_text(FIXTURE_MD, encoding="utf-8")
    result = read_fundamental_research("NVDA", search_dir=tmp_path)
    assert result["ticker"] == "NVDA"
    assert result["trigger_source"] == "SMM_GOLDEN_EP"
    assert "Revenue beat by 8%" in result["body"]
    assert "Export restrictions" in result["body"]


def test_list_fundamental_research_tickers(tmp_path):
    for name in ["nvda_fundamental.md", "aapl_fundamental.md", "other.txt"]:
        (tmp_path / name).write_text(FIXTURE_MD, encoding="utf-8")
    tickers = list_fundamental_research_tickers(search_dir=tmp_path)
    assert set(tickers) == {"NVDA", "AAPL"}
```

**Step 2: Run to verify failure**

```bash
cd c:\Users\User\Documents\GitHub\fundman-jarvis
pytest tests/test_fundamental_research_reader.py -q
```
Expected: `ImportError: cannot import name 'read_fundamental_research'`

**Step 3: Add reader functions to external_scrapers.py**

Add after the existing scraper functions:

```python
# ── Fundamental Research (NotebookLM MD output) ──────────────

_FUNDAMENTAL_RESEARCH_DEFAULT_DIR = Path(
    os.getenv(
        "NOTION_AUTOPUBLISH_DIR",
        Path(__file__).parent.parent / "notion-autopublish",
    )
) / "scraped_data" / "notebooklm"


def read_fundamental_research(ticker: str, search_dir: Path | None = None) -> dict:
    """
    Read a fundamental research MD file for a given ticker.
    Returns dict with 'ticker', 'frontmatter', 'body', and raw 'text'.
    Returns empty dict if not found.
    """
    import frontmatter  # python-frontmatter

    base_dir = search_dir or _FUNDAMENTAL_RESEARCH_DEFAULT_DIR
    path = base_dir / f"{ticker.lower()}_fundamental.md"
    if not path.exists():
        return {}
    post = frontmatter.load(str(path))
    return {
        "ticker": post.get("ticker", ticker.upper()),
        "sector": post.get("sector", ""),
        "trigger_source": post.get("trigger_source", ""),
        "trigger_signal": post.get("trigger_signal", ""),
        "notebook_id": post.get("notebook_id", ""),
        "synced_at": post.get("synced_at", ""),
        "youtube_urls": post.get("youtube_urls", []),
        "body": post.content,
        "text": path.read_text(encoding="utf-8"),
    }


def list_fundamental_research_tickers(search_dir: Path | None = None) -> list[str]:
    """Return list of tickers that have a fundamental research MD file."""
    base_dir = search_dir or _FUNDAMENTAL_RESEARCH_DEFAULT_DIR
    if not base_dir.exists():
        return []
    return [
        p.stem.replace("_fundamental", "").upper()
        for p in base_dir.glob("*_fundamental.md")
    ]
```

**Step 4: Run tests**

```bash
pytest tests/test_fundamental_research_reader.py -q
```
Expected: PASS.

**Step 5: Commit in fundman-jarvis**

```bash
git add external_scrapers.py tests/test_fundamental_research_reader.py
git commit -m "feat: add fundamental research reader for NotebookLM MD output"
```

---

### Task 5: Document the manual auth dependency and live verification

**Files:**
- Modify: `README.md` (notion-autopublish)

**Step 1: Add NotebookLM fundamental research section to README**

Under the existing NotebookLM section (or create one), document:

```markdown
## NotebookLM: Signal-Triggered Fundamental Research

### One-time setup

```bash
# Install the library (if not already in requirements.txt)
pip install "notebooklm-py[browser]"

# Log in once — opens a browser window for Google sign-in
python -m notebooklm login

# Create one NLM notebook per ticker at notebooklm.google.com
# Copy the notebook ID from the URL:  .../notebook/<NOTEBOOK_ID>
```

### Running research

```bash
# Manual trigger (e.g. after DeepVue flags NVDA):
python scrape_fundamental_research.py \
    --ticker NVDA \
    --sector semiconductors \
    --trigger-source DEEPVUE \
    --trigger-signal momentum_breakout \
    --notebook-id <YOUR_NOTEBOOK_ID> \
    --youtube "https://www.youtube.com/watch?v=<earnings_call_id>" \
    --youtube "https://www.youtube.com/watch?v=<analyst_video_id>"

# Or via signal file (for automated SMM/DeepVue triggers):
python scrape_fundamental_research.py \
    --signal-file path/to/smm_signal.json \
    --notebook-id <YOUR_NOTEBOOK_ID>
```

### Output

`scraped_data/notebooklm/{ticker_lower}_fundamental.md` — human-readable MD with
YAML frontmatter. Open directly in any editor; fundman-jarvis reads it via
`external_scrapers.read_fundamental_research(ticker)`.

### Auth note

NotebookLM uses cookie-based sessions (1–2 hour expiry). Re-run `python -m notebooklm login`
if you get auth errors. Store the storage path in `NOTEBOOKLM_STORAGE_PATH` env var.

### Interactive / ad-hoc path

Use the `notebooklm-skill-master` skill in Claude Code to query NLM notebooks
directly mid-conversation — no script needed for one-off analyst questions.
```

**Step 2: Run final verification**

```bash
# In notion-autopublish
pytest tests/test_fundamental_notebooklm.py -q
python -m py_compile scrape_fundamental_research.py fundamental_research/notebooklm_research.py

# In fundman-jarvis
pytest tests/test_fundamental_research_reader.py -q
```
Expected: all PASS, no syntax errors.

**Step 3: Live smoke test (requires prior `notebooklm login` and a real notebook ID)**

```bash
# Dry run: will fail gracefully with auth message if not logged in
python scrape_fundamental_research.py \
    --ticker NVDA \
    --sector semiconductors \
    --trigger-source MANUAL \
    --trigger-signal ad_hoc_test \
    --notebook-id <YOUR_NOTEBOOK_ID> \
    --youtube "https://www.youtube.com/watch?v=6JCqUhMsPeM"
```
Expected: either saves `scraped_data/notebooklm/nvda_fundamental.md` (success) or
prints an explicit auth-required error (not logged in).

**Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: document fundamental research NotebookLM setup and auth"
```

---

## Future automation hooks (not in scope now)

- **SMM Golden EP → signal file**: When SMM outputs a sector signal, auto-generate a `signal.json` and call `scrape_fundamental_research.py` from `daily_reminders.py`
- **DeepVue panel → signal file**: When DeepVue image analysis identifies a sector breakout, extract the ticker and trigger research
- **FundamentalResearchExpert**: A new fundman-jarvis expert that reads all `*_fundamental.md` files and contributes to the CIO MOE router

These are intentionally deferred — build the plumbing first, automate the triggers once the output format is validated.
