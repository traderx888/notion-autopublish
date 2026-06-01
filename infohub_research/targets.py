"""Unify NotebookLM equity signals with Info Hub-specific extractors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from notebooklm_research.signals import collect_research_targets

from .screening_sources import (
    extract_dcb_targets,
    extract_liquidity_targets,
    extract_polymarket_targets,
)


# Lower number = higher priority. Used both for ordering and for dedup
# tie-breaking when two extractors emit the same slug.
_KIND_PRIORITY = {
    "ticker": 0,
    "sector": 1,
    "event_topic": 2,
    "macro_keyword": 3,
}


@dataclass
class ScreeningTarget:
    kind: str
    slug: str
    keywords: list[str]
    source: str
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return _KIND_PRIORITY.get(self.kind, 99)

    def signal_dict(self) -> dict[str, Any]:
        """Original screening payload, for downstream traceability."""
        return dict(self.raw)


def _slugify_ticker(ticker: str) -> str:
    return ticker.lower().replace(".", "_").replace(":", "_")


def _wrap_notebooklm_target(item: dict[str, Any]) -> ScreeningTarget:
    """Adapt a notebooklm_research signal dict into a ScreeningTarget."""
    ticker = item["ticker"]
    keywords = [ticker]
    # SemiAnalysis/FOMO mentions also include a context snippet — pick the
    # first noun-ish word from it as a soft secondary keyword.
    return ScreeningTarget(
        kind="ticker",
        slug=_slugify_ticker(ticker),
        keywords=keywords,
        source=item.get("source", "notebooklm_signal"),
        note=item.get("note") or item.get("grade") or "",
        raw=item,
    )


def _wrap_screening(item: dict[str, Any]) -> ScreeningTarget:
    return ScreeningTarget(
        kind=item["kind"],
        slug=item["slug"],
        keywords=list(item.get("keywords") or []),
        source=item.get("source", ""),
        note=item.get("note", ""),
        raw=item,
    )


def collect_all_targets(
    *,
    scraped_dir: Path | None = None,
    fundman_data_dir: Path | None = None,
    outputs_dir: Path | None = None,
    max_per_kind: int = 5,
    notebooklm_max: int = 8,
) -> list[ScreeningTarget]:
    """Aggregate every screening source into a single typed list.

    The notebooklm signal extractor handles SMM SWAN, SemiAnalysis, FOMO,
    DeepVue stage and capscreen. The three local extractors add
    Dailychartbook, Polymarket, and the H-Model liquidity tracker.

    The result is deduped by ``(kind, slug)``, ranked by kind priority then
    by source priority within each kind, and capped at ``max_per_kind``.
    """
    scraped_dir = scraped_dir or Path("scraped_data")
    outputs_dir = outputs_dir or Path("outputs")

    raw: list[ScreeningTarget] = []

    # 1. Equity tickers (reuses notebooklm_research)
    notebooklm_items = collect_research_targets(
        scraped_dir=scraped_dir,
        fundman_data_dir=fundman_data_dir,
        max_targets=notebooklm_max,
    )
    raw.extend(_wrap_notebooklm_target(it) for it in notebooklm_items)

    # 2. Dailychartbook macro family signals
    dcb_path = scraped_dir / "dailychartbook" / "dailychartbook_readings_latest.json"
    raw.extend(_wrap_screening(it) for it in extract_dcb_targets(dcb_path))

    # 3. Polymarket trader event topics
    poly_path = scraped_dir / "polymarketanalytics" / "trader_signals_latest.json"
    raw.extend(_wrap_screening(it) for it in extract_polymarket_targets(poly_path))

    # 4. Liquidity tracker H-Model
    liq_path = outputs_dir / "liquidity" / "h_model_latest.json"
    raw.extend(_wrap_screening(it) for it in extract_liquidity_targets(liq_path))

    # Dedup by (kind, slug). Same slug across kinds is allowed.
    deduped: dict[tuple[str, str], ScreeningTarget] = {}
    for t in raw:
        if not t.keywords:
            continue
        key = (t.kind, t.slug)
        if key not in deduped:
            deduped[key] = t

    # Cap per kind, preserving discovery order within each kind.
    by_kind: dict[str, list[ScreeningTarget]] = {}
    for t in deduped.values():
        by_kind.setdefault(t.kind, []).append(t)

    out: list[ScreeningTarget] = []
    for kind in sorted(by_kind.keys(), key=lambda k: _KIND_PRIORITY.get(k, 99)):
        out.extend(by_kind[kind][:max_per_kind])
    return out


def filter_kinds(
    targets: Iterable[ScreeningTarget],
    only_kinds: Iterable[str] | None,
) -> list[ScreeningTarget]:
    if not only_kinds:
        return list(targets)
    allow = {k.strip() for k in only_kinds if k and k.strip()}
    return [t for t in targets if t.kind in allow]
