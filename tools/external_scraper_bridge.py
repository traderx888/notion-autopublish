from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_external_scrapers_module(fundman_root: Path):
    module_path = fundman_root / "external_scrapers.py"
    if not module_path.exists():
        raise FileNotFoundError(f"Missing fundman-jarvis inventory: {module_path}")
    if str(fundman_root) not in sys.path:
        sys.path.insert(0, str(fundman_root))
    os.environ.setdefault("NOTION_AUTOPUBLISH_DIR", str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("fundman_external_scrapers", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _as_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _invoke(module: Any, source_id: str, params: dict[str, Any]) -> Any:
    if source_id == "telegram_fnd":
        return module.scrape_telegram_channel(max_messages=_as_int(params.get("max_messages"), 20))
    # DISABLED — Conchstreet 失衡排行 alert permanently retired
    if source_id == "conchstreet_positioning":
        return {"charts": [], "status": "disabled"}
    if source_id == "wscn_live":
        return module.scrape_wscn_live(
            hours=_as_int(params.get("hours"), 4),
            max_pages=_as_int(params.get("max_pages"), 8),
            limit_per_page=_as_int(params.get("limit_per_page"), 20),
        )
    if source_id == "twitter_handles":
        handles = _as_list(params.get("handles"))
        if not handles:
            raise ValueError("twitter_handles requires handles")
        return module.scrape_twitter(handles=handles, limit=_as_int(params.get("limit"), 20))
    if source_id == "twitter_search":
        query = str(params.get("query") or "").strip()
        if not query:
            raise ValueError("twitter_search requires query")
        return module.scrape_twitter_search(query=query, limit=_as_int(params.get("limit"), 100))
    if source_id == "threads_handles":
        handles = _as_list(params.get("handles"))
        if not handles:
            raise ValueError("threads_handles requires handles")
        return module.scrape_threads(handles=handles, limit=_as_int(params.get("limit"), 20))
    if source_id == "notebooklm_research":
        tickers = _as_list(params.get("tickers"))
        return module.scrape_notebooklm_research(
            tickers=tickers or None,
            from_signals=_as_bool(params.get("from_signals")),
            max_tickers=_as_int(params.get("max_tickers"), 5),
            max_youtube=_as_int(params.get("max_youtube"), 3),
        )
    if source_id == "infohub_events":
        raw_events = params.get("events")
        if raw_events is None and params.get("events_json"):
            raw_events = json.loads(str(params["events_json"]))
        if not isinstance(raw_events, list) or not raw_events:
            raise ValueError("infohub_events requires a non-empty events list")
        return module.run_infohub_events(
            raw_events,
            sources=_as_list(params.get("sources")) or None,
            days=_as_int(params.get("days"), 1),
            max_items_per_source=_as_int(params.get("max_items_per_source"), 3),
        )
    raise KeyError(f"Unsupported bridge source_id: {source_id}")


def _summarize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, Path):
        return {"result_type": "path", "path": str(result), "exists": result.exists()}
    if isinstance(result, list):
        return {"result_type": "list", "count": len(result)}
    if isinstance(result, dict):
        return {"result_type": "dict", "keys": sorted(result.keys()), "count": len(result)}
    return {"result_type": type(result).__name__, "value": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke bridge-backed external scraper actions from fundman-jarvis.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--fundman-root", type=Path, required=True)
    parser.add_argument("--params-json", default="{}")
    args = parser.parse_args()

    params = json.loads(args.params_json)
    module = _load_external_scrapers_module(args.fundman_root)
    result = _invoke(module, args.source_id, params)
    print(json.dumps(_summarize_result(result), ensure_ascii=False))
    if result in (None, [], {}):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
