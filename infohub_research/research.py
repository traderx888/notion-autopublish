"""End-to-end orchestration: target → watch profile → crawls → JSON output."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .bridge import InfoHubClient, InfoHubError
from .profile_builder import build_profile_spec
from .targets import ScreeningTarget, collect_all_targets, filter_kinds


_LOG = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def research_target(
    client: InfoHubClient,
    target: ScreeningTarget,
    *,
    output_dir: Path,
    days: int = 3,
    max_items_per_source: int = 5,
) -> dict[str, Any]:
    """Run the full pipeline for one target and write its JSON."""
    spec = build_profile_spec(target)

    # 1. Activate the umbrella watch profile (idempotent / merges).
    profile = client.activate_profile(spec)

    # 2. Fan out crawls to each preset source.
    items_by_source: dict[str, list[dict[str, Any]]] = {}
    crawl_summaries: dict[str, dict[str, Any]] = {}
    crawl_errors: dict[str, str] = {}
    crawl_keywords = spec.get("crawl_keywords") or list(target.keywords)

    for source in spec.get("sources", []):
        try:
            crawl_summaries[source] = client.crawl_run(
                source=source,
                keywords=crawl_keywords,
                days=days,
                max_items=max_items_per_source,
            )
            items_by_source[source] = client.items_latest(
                source=source,
                limit=max_items_per_source,
            )
        except InfoHubError as exc:
            crawl_errors[source] = str(exc)
            items_by_source[source] = []
            _LOG.warning("crawl failed for %s/%s: %s", target.slug, source, exc)

    payload = {
        "slug": target.slug,
        "kind": target.kind,
        "researched_at": _now_iso(),
        "screening_signal": target.signal_dict(),
        "infohub_profile": profile,
        "profile_spec": {
            "domain": spec.get("domain"),
            "theme": spec.get("theme"),
            "focus": spec.get("focus"),
            "queries": spec.get("queries"),
            "sources": spec.get("sources"),
        },
        "keywords": list(target.keywords),
        "crawl_summaries": crawl_summaries,
        "crawl_errors": crawl_errors,
        "items_by_source": items_by_source,
        "total_items": sum(len(v) for v in items_by_source.values()),
    }

    out_path = output_dir / f"{target.slug}_news.json"
    _write_json(out_path, payload)
    return payload


def run_pipeline(
    *,
    scraped_dir: Path,
    fundman_data_dir: Path | None,
    outputs_dir: Path,
    output_dir: Path,
    client: InfoHubClient,
    max_per_kind: int = 5,
    days: int = 3,
    max_items_per_source: int = 5,
    only_kinds: Iterable[str] | None = None,
    targets: list[ScreeningTarget] | None = None,
) -> dict[str, Any]:
    """Drive the full screen → research → JSON loop.

    Returns a summary dict with per-target status; also writes
    ``output_dir/index.json`` so downstream consumers can discover what was
    refreshed in this run.
    """
    if targets is None:
        targets = collect_all_targets(
            scraped_dir=scraped_dir,
            fundman_data_dir=fundman_data_dir,
            outputs_dir=outputs_dir,
            max_per_kind=max_per_kind,
        )
    targets = filter_kinds(targets, only_kinds)

    summary: dict[str, Any] = {
        "started_at": _now_iso(),
        "target_count": len(targets),
        "results": [],
        "errors": [],
    }

    index: dict[str, Any] = {}
    for target in targets:
        try:
            result = research_target(
                client,
                target,
                output_dir=output_dir,
                days=days,
                max_items_per_source=max_items_per_source,
            )
        except Exception as exc:  # noqa: BLE001 — keep batch alive
            _LOG.exception("research_target failed for %s", target.slug)
            summary["errors"].append({"slug": target.slug, "error": str(exc)})
            continue

        summary["results"].append({
            "slug": target.slug,
            "kind": target.kind,
            "total_items": result.get("total_items", 0),
            "profile_key": (result.get("infohub_profile") or {}).get("profile_key"),
        })
        index[target.slug] = {
            "kind": target.kind,
            "profile_key": (result.get("infohub_profile") or {}).get("profile_key"),
            "total_items": result.get("total_items", 0),
            "researched_at": result["researched_at"],
            "path": str((output_dir / f"{target.slug}_news.json").as_posix()),
        }

    summary["finished_at"] = _now_iso()
    _write_json(output_dir / "index.json", {
        "generated_at": summary["finished_at"],
        "targets": index,
    })
    return summary
