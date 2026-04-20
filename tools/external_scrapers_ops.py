from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


HKT = timezone(timedelta(hours=8))
OPS_STATE_RELATIVE_PATH = Path("scraped_data") / "ops" / "external_scraper_runs.json"

FAMILY_ORDER = [
    "substack",
    "seekingalpha",
    "deepvue",
    "macromicro",
    "institutional",
    "liquidity",
    "dailychartbook",
    "ciovacco",
    "notebooklm_registry",
    "telegram_fnd",
    # "conchstreet_positioning",  # DISABLED — Conchstreet 失衡排行 alert permanently retired
    "wscn_live",
]

ADVANCED_TOOL_ORDER = [
    "twitter_handles",
    "twitter_search",
    "threads_handles",
    "notebooklm_research",
    "infohub_events",
]


def _now_hkt(now_iso: str | None = None) -> datetime:
    if now_iso:
        parsed = datetime.fromisoformat(now_iso)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=HKT)
        return parsed.astimezone(HKT)
    return datetime.now(HKT)


def _entry(
    source_id: str,
    display_name: str,
    family_id: str,
    repo_owner: str,
    kind: str,
    artifact_paths: list[str],
    freshness_rule: dict[str, Any] | None,
    action_kind: str | None,
    action_command: list[str] | None,
    *,
    session_service: str | None = None,
    input_schema: list[dict[str, Any]] | None = None,
    extra_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "display_name": display_name,
        "family_id": family_id,
        "repo_owner": repo_owner,
        "kind": kind,
        "artifact_paths": artifact_paths,
        "freshness_rule": freshness_rule or {"type": "none"},
        "action_kind": action_kind,
        "action_command": action_command,
        "session_service": session_service,
        "input_schema": input_schema or [],
        "extra_actions": extra_actions or [],
    }


def _notion_entry(
    source_id: str,
    display_name: str,
    family_id: str,
    kind: str,
    artifact_paths: list[str],
    freshness_rule: dict[str, Any] | None,
    action_kind: str | None,
    action_command: list[str] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    return _entry(
        source_id,
        display_name,
        family_id,
        "notion-autopublish",
        kind,
        artifact_paths,
        freshness_rule,
        action_kind,
        action_command,
        **kwargs,
    )


def _fundman_entry(
    source_id: str,
    display_name: str,
    family_id: str,
    kind: str,
    artifact_paths: list[str],
    freshness_rule: dict[str, Any] | None,
    action_kind: str | None,
    action_command: list[str] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    return _entry(
        source_id,
        display_name,
        family_id,
        "fundman-jarvis",
        kind,
        artifact_paths,
        freshness_rule,
        action_kind,
        action_command,
        **kwargs,
    )


def build_registry(repo_root: Path, fundman_root: Path) -> dict[str, dict[str, Any]]:
    del repo_root, fundman_root

    registry: dict[str, dict[str, Any]] = {}

    substack_paths = [
        "scraped_data/substack_authors/capitalwars_latest.txt",
        "scraped_data/substack_authors/fomosoc_latest.txt",
        "scraped_data/substack_authors/semianalysis_latest.txt",
        "scraped_data/substack_authors/finallynitin_latest.txt",
        "scraped_data/substack_authors/sysls_latest.txt",
    ]
    registry["substack"] = _notion_entry(
        "substack",
        "Substack",
        "substack",
        "auth_service",
        substack_paths,
        {"type": "freshest_of", "max_hours": 72},
        "relogin",
        ["daily_login_ceremony.py", "--services", "substack", "--no-telegram"],
        session_service="substack",
    )
    registry["substack.capitalwars"] = _notion_entry(
        "substack.capitalwars",
        "Capital Wars",
        "substack",
        "artifact_only",
        ["scraped_data/substack_authors/capitalwars_latest.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )
    registry["substack.fomosoc"] = _notion_entry(
        "substack.fomosoc",
        "Fomosoc",
        "substack",
        "artifact_only",
        ["scraped_data/substack_authors/fomosoc_latest.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )
    registry["substack.semianalysis"] = _notion_entry(
        "substack.semianalysis",
        "SemiAnalysis",
        "substack",
        "artifact_only",
        ["scraped_data/substack_authors/semianalysis_latest.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )
    registry["substack.finallynitin"] = _notion_entry(
        "substack.finallynitin",
        "Finally Nitin",
        "substack",
        "artifact_only",
        ["scraped_data/substack_authors/finallynitin_latest.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )
    registry["substack.sysls"] = _notion_entry(
        "substack.sysls",
        "Systematic LS",
        "substack",
        "artifact_only",
        ["scraped_data/substack_authors/sysls_latest.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )

    seeking_alpha_paths = [
        "scraped_data/sa_group_predictive_models.txt",
        "scraped_data/sa_group_gamma_charm.txt",
    ]
    registry["seekingalpha"] = _notion_entry(
        "seekingalpha",
        "Seeking Alpha",
        "seekingalpha",
        "auth_service",
        seeking_alpha_paths,
        {"type": "freshest_of", "max_hours": 72},
        "relogin",
        ["daily_login_ceremony.py", "--services", "seekingalpha", "--no-telegram"],
        session_service="seekingalpha",
    )
    registry["seekingalpha.p_model"] = _notion_entry(
        "seekingalpha.p_model",
        "P-Model",
        "seekingalpha",
        "artifact_only",
        ["scraped_data/sa_group_predictive_models.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )
    registry["seekingalpha.gamma_charm"] = _notion_entry(
        "seekingalpha.gamma_charm",
        "Gamma Charm",
        "seekingalpha",
        "artifact_only",
        ["scraped_data/sa_group_gamma_charm.txt"],
        {"type": "mtime_hours", "max_hours": 72},
        None,
        None,
    )

    registry["deepvue"] = _notion_entry(
        "deepvue",
        "DeepVue",
        "deepvue",
        "auth_service",
        [
            "scraped_data/deepvue/market_overview.json",
            "scraped_data/deepvue/preopen.json",
        ],
        {"type": "freshest_of", "max_hours": 24},
        "relogin",
        ["daily_login_ceremony.py", "--services", "deepvue", "--no-telegram"],
        session_service="deepvue",
    )
    registry["deepvue.market_overview"] = _notion_entry(
        "deepvue.market_overview",
        "Market Overview",
        "deepvue",
        "artifact_only",
        ["scraped_data/deepvue/market_overview.json"],
        {"type": "json_timestamp_same_day", "field": "timestamp", "max_hours": 24},
        None,
        None,
    )
    registry["deepvue.preopen"] = _notion_entry(
        "deepvue.preopen",
        "Pre-open",
        "deepvue",
        "artifact_only",
        ["scraped_data/deepvue/preopen.json"],
        {"type": "json_timestamp_same_day", "field": "timestamp", "max_hours": 24},
        None,
        None,
    )

    registry["macromicro"] = _notion_entry(
        "macromicro",
        "MacroMicro",
        "macromicro",
        "auth_service",
        ["scraped_data/macromicro/macromicro_latest.json"],
        {"type": "mtime_hours", "max_hours": 48},
        "relogin",
        ["scrape_macromicro.py", "--login"],
        session_service="macromicro",
        extra_actions=[
            {
                "action_name": "run",
                "label": "Run now",
                "action_kind": "run",
                "action_command": ["scrape_macromicro.py"],
            }
        ],
    )

    institutional_paths = [
        "scraped_data/institutional/goldmansachs_latest.txt",
        "scraped_data/institutional/citadelsecurities_latest.txt",
        "scraped_data/institutional/morganstanley_latest.txt",
        "scraped_data/institutional/institutional_latest.json",
    ]
    registry["institutional"] = _notion_entry(
        "institutional",
        "Institutional",
        "institutional",
        "run_service",
        institutional_paths,
        {"type": "freshest_of", "max_hours": 48},
        "run",
        ["scrape_institutional.py", "--headless"],
    )
    registry["institutional.goldmansachs"] = _notion_entry(
        "institutional.goldmansachs",
        "Goldman Sachs",
        "institutional",
        "artifact_only",
        ["scraped_data/institutional/goldmansachs_latest.txt"],
        {"type": "mtime_hours", "max_hours": 48},
        None,
        None,
    )
    registry["institutional.citadelsecurities"] = _notion_entry(
        "institutional.citadelsecurities",
        "Citadel Securities",
        "institutional",
        "artifact_only",
        ["scraped_data/institutional/citadelsecurities_latest.txt"],
        {"type": "mtime_hours", "max_hours": 48},
        None,
        None,
    )
    registry["institutional.morganstanley"] = _notion_entry(
        "institutional.morganstanley",
        "Morgan Stanley",
        "institutional",
        "artifact_only",
        ["scraped_data/institutional/morganstanley_latest.txt"],
        {"type": "mtime_hours", "max_hours": 48},
        None,
        None,
    )

    registry["liquidity"] = _notion_entry(
        "liquidity",
        "Liquidity",
        "liquidity",
        "run_service",
        ["outputs/liquidity/liquidity_tracker_latest.json"],
        {"type": "mtime_hours", "max_hours": 26},
        "run",
        ["liquidity_tracker.py", "run"],
    )
    registry["dailychartbook"] = _notion_entry(
        "dailychartbook",
        "Daily Chartbook",
        "dailychartbook",
        "run_service",
        ["scraped_data/dailychartbook/dailychartbook_readings_latest.json"],
        {"type": "mtime_hours", "max_hours": 36},
        "run",
        ["scrape_dailychartbook.py"],
    )
    registry["ciovacco"] = _notion_entry(
        "ciovacco",
        "Ciovacco",
        "ciovacco",
        "run_service",
        ["scraped_data/ciovacco/ciovacco_latest.json"],
        {"type": "mtime_hours", "max_hours": 168},
        "run",
        ["scrape_ciovacco.py"],
    )
    registry["notebooklm_registry"] = _notion_entry(
        "notebooklm_registry",
        "NotebookLM Registry",
        "notebooklm_registry",
        "auth_service",
        ["scraped_data/notebooklm/notebook_registry.json"],
        {"type": "mtime_hours", "max_hours": 168},
        "relogin",
        ["daily_login_ceremony.py", "--services", "notebooklm", "--no-telegram"],
        session_service="notebooklm",
    )

    registry["telegram_fnd"] = _fundman_entry(
        "telegram_fnd",
        "Telegram FND",
        "telegram_fnd",
        "run_service",
        ["data/telegram_fnd_headlines.json"],
        {"type": "mtime_hours", "max_hours": 24},
        "run",
        None,
    )
    # DISABLED — Conchstreet 失衡排行 alert permanently retired
    # registry["conchstreet_positioning"] = _fundman_entry(
    #     "conchstreet_positioning",
    #     "Conchstreet Positioning",
    #     "conchstreet_positioning",
    #     "run_service",
    #     ["data/telegram_conchstreet_positioning.json"],
    #     {"type": "mtime_hours", "max_hours": 24},
    #     "run",
    #     None,
    # )
    registry["wscn_live"] = _fundman_entry(
        "wscn_live",
        "WSCN Live",
        "wscn_live",
        "run_service",
        ["data/wscn_headlines.json"],
        {"type": "mtime_hours", "max_hours": 12},
        "run",
        None,
    )

    registry["twitter_handles"] = _notion_entry(
        "twitter_handles",
        "Twitter Handles",
        "twitter_handles",
        "parameterized_tool",
        [],
        {"type": "none"},
        "run",
        None,
        input_schema=[
            {"name": "handles", "label": "Handles", "type": "text", "placeholder": "@spotgamma,@zaborniki"},
            {"name": "limit", "label": "Limit", "type": "number", "default": 20},
        ],
    )
    registry["twitter_search"] = _notion_entry(
        "twitter_search",
        "Twitter Search",
        "twitter_search",
        "parameterized_tool",
        [],
        {"type": "none"},
        "run",
        None,
        input_schema=[
            {"name": "query", "label": "Query", "type": "text", "placeholder": "macro liquidity"},
            {"name": "limit", "label": "Limit", "type": "number", "default": 25},
        ],
    )
    registry["threads_handles"] = _notion_entry(
        "threads_handles",
        "Threads Handles",
        "threads_handles",
        "parameterized_tool",
        [],
        {"type": "none"},
        "run",
        None,
        input_schema=[
            {"name": "handles", "label": "Handles", "type": "text", "placeholder": "@zuck"},
            {"name": "limit", "label": "Limit", "type": "number", "default": 20},
        ],
    )
    registry["notebooklm_research"] = _notion_entry(
        "notebooklm_research",
        "NotebookLM Research",
        "notebooklm_research",
        "parameterized_tool",
        [],
        {"type": "none"},
        "run",
        None,
        input_schema=[
            {"name": "tickers", "label": "Tickers", "type": "text", "placeholder": "NVDA,TSLA"},
            {"name": "from_signals", "label": "From signals", "type": "checkbox", "default": False},
            {"name": "max_tickers", "label": "Max tickers", "type": "number", "default": 5},
            {"name": "max_youtube", "label": "Max YouTube", "type": "number", "default": 3},
        ],
    )
    registry["infohub_events"] = _notion_entry(
        "infohub_events",
        "InfoHub Events",
        "infohub_events",
        "parameterized_tool",
        [],
        {"type": "none"},
        "run",
        None,
        input_schema=[
            {"name": "events_json", "label": "Events JSON", "type": "textarea", "placeholder": "[{\"name\":\"CPI\"}]"},
            {"name": "sources", "label": "Sources", "type": "text", "placeholder": "reuters,wsj"},
            {"name": "days", "label": "Days", "type": "number", "default": 1},
            {"name": "max_items_per_source", "label": "Items/source", "type": "number", "default": 3},
        ],
    )

    return registry


def get_ops_state_path(repo_root: Path) -> Path:
    return Path(repo_root) / OPS_STATE_RELATIVE_PATH


def load_ops_state(repo_root: Path) -> dict[str, Any]:
    state_path = get_ops_state_path(repo_root)
    if not state_path.exists():
        return {"jobs": {}}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"jobs": {}}
    if not isinstance(payload, dict):
        return {"jobs": {}}
    jobs = payload.get("jobs")
    if not isinstance(jobs, dict):
        return {"jobs": {}}
    return {"jobs": jobs}


def save_ops_state(repo_root: Path, jobs: dict[str, Any]) -> None:
    state_path = get_ops_state_path(repo_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"jobs": jobs, "updated_at": _now_hkt().isoformat(timespec="seconds")}
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _owner_root(entry: dict[str, Any], repo_root: Path, fundman_root: Path) -> Path:
    return repo_root if entry["repo_owner"] == "notion-autopublish" else fundman_root


def _resolve_paths(entry: dict[str, Any], repo_root: Path, fundman_root: Path) -> list[Path]:
    root = _owner_root(entry, repo_root, fundman_root)
    return [root / relative for relative in entry.get("artifact_paths", [])]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _status_from_stamp(service: str | None, repo_root: Path, now: datetime) -> dict[str, Any] | None:
    if not service:
        return None

    stamp_path = repo_root / "browser" / "sessions" / service / "ceremony_stamp.json"
    payload = _read_json(stamp_path)
    if payload is None:
        return {
            "service": service,
            "status": "missing",
            "stamp_path": str(stamp_path),
            "date": None,
            "login_at": None,
            "scrape_ok": None,
            "check_only": None,
            "outputs": [],
        }

    date_value = str(payload.get("date") or "")
    scrape_ok = payload.get("scrape_ok")
    check_only = payload.get("check_only")
    status = "missing"
    if date_value == now.date().isoformat():
        if check_only:
            status = "check_only"
        elif scrape_ok:
            status = "ok"
        else:
            status = "failed"
    else:
        status = "stale"

    return {
        "service": service,
        "status": status,
        "stamp_path": str(stamp_path),
        "date": date_value or None,
        "login_at": payload.get("login_at"),
        "scrape_ok": scrape_ok,
        "check_only": check_only,
        "outputs": payload.get("outputs") or [],
    }


def _evaluate_freshness(
    entry: dict[str, Any],
    repo_root: Path,
    fundman_root: Path,
    now: datetime,
) -> dict[str, Any]:
    rule = entry.get("freshness_rule") or {"type": "none"}
    paths = _resolve_paths(entry, repo_root, fundman_root)
    rule_type = rule.get("type", "none")

    if rule_type == "none":
        return {"status": "missing", "checked_at": now.isoformat(timespec="seconds"), "artifacts": entry["artifact_paths"]}

    if not paths:
        return {"status": "missing", "checked_at": now.isoformat(timespec="seconds"), "artifacts": []}

    if rule_type == "mtime_hours":
        path = paths[0]
        if not path.exists():
            return {"status": "missing", "checked_at": now.isoformat(timespec="seconds"), "artifacts": entry["artifact_paths"]}
        age_hours = (now.timestamp() - path.stat().st_mtime) / 3600
        status = "ok" if age_hours <= float(rule.get("max_hours", 24)) else "stale"
        return {
            "status": status,
            "checked_at": now.isoformat(timespec="seconds"),
            "artifact": str(path),
            "artifacts": entry["artifact_paths"],
            "latest_at": datetime.fromtimestamp(path.stat().st_mtime, HKT).isoformat(timespec="seconds"),
            "age_hours": round(age_hours, 1),
        }

    if rule_type == "json_timestamp_same_day":
        path = paths[0]
        if not path.exists():
            return {"status": "missing", "checked_at": now.isoformat(timespec="seconds"), "artifacts": entry["artifact_paths"]}
        payload = _read_json(path)
        timestamp_field = str(rule.get("field") or "timestamp")
        captured_at = payload.get(timestamp_field) if payload else None
        try:
            parsed = datetime.fromisoformat(str(captured_at))
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None and parsed.tzinfo is not None:
            parsed = parsed.astimezone(HKT)
        status = "ok" if parsed and parsed.date() == now.date() else "stale"
        return {
            "status": status,
            "checked_at": now.isoformat(timespec="seconds"),
            "artifact": str(path),
            "artifacts": entry["artifact_paths"],
            "latest_at": parsed.isoformat(timespec="seconds") if parsed else None,
        }

    if rule_type == "freshest_of":
        existing = [path for path in paths if path.exists()]
        if not existing:
            return {"status": "missing", "checked_at": now.isoformat(timespec="seconds"), "artifacts": entry["artifact_paths"]}
        freshest = max(existing, key=lambda item: item.stat().st_mtime)
        age_hours = (now.timestamp() - freshest.stat().st_mtime) / 3600
        status = "ok" if age_hours <= float(rule.get("max_hours", 24)) else "stale"
        return {
            "status": status,
            "checked_at": now.isoformat(timespec="seconds"),
            "artifact": str(freshest),
            "artifacts": entry["artifact_paths"],
            "latest_at": datetime.fromtimestamp(freshest.stat().st_mtime, HKT).isoformat(timespec="seconds"),
            "age_hours": round(age_hours, 1),
        }

    return {"status": "missing", "checked_at": now.isoformat(timespec="seconds"), "artifacts": entry["artifact_paths"]}


def _job_to_status(job: dict[str, Any] | None) -> str | None:
    if not job:
        return None
    state = str(job.get("state") or "")
    if state == "running":
        return "running"
    if state == "failed":
        return "failed"
    if state == "succeeded":
        return "ok"
    return None


def _child_payload(
    entry: dict[str, Any],
    repo_root: Path,
    fundman_root: Path,
    now: datetime,
) -> dict[str, Any]:
    freshness = _evaluate_freshness(entry, repo_root, fundman_root, now)
    return {
        "source_id": entry["source_id"],
        "display_name": entry["display_name"],
        "family_id": entry["family_id"],
        "kind": entry["kind"],
        "status": freshness["status"],
        "repo_owner": entry["repo_owner"],
        "artifacts": entry["artifact_paths"],
        "freshness": freshness,
    }


def _aggregate_family_status(
    children: list[dict[str, Any]],
    family_freshness: dict[str, Any],
    auth: dict[str, Any] | None,
    job: dict[str, Any] | None,
) -> str:
    job_status = _job_to_status(job)
    if job_status == "running":
        return "running"
    if job_status == "failed":
        return "failed"
    if auth and auth.get("status") == "failed":
        return "failed"
    if children:
        child_statuses = [child["status"] for child in children]
        if "failed" in child_statuses:
            return "failed"
        if "missing" in child_statuses:
            return "missing"
        if "stale" in child_statuses:
            return "stale"
        return "ok"
    if family_freshness["status"] != "missing":
        return str(family_freshness["status"])
    if auth:
        return str(auth.get("status") or "missing")
    return "missing"


def _family_catalog_entry(entry: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    children = [
        child
        for child in registry.values()
        if child["family_id"] == entry["source_id"] and child["source_id"] != entry["source_id"]
    ]
    children.sort(key=lambda item: item["display_name"].lower())
    return {
        "source_id": entry["source_id"],
        "display_name": entry["display_name"],
        "family_id": entry["family_id"],
        "kind": entry["kind"],
        "repo_owner": entry["repo_owner"],
        "action_kind": entry["action_kind"],
        "artifacts": entry["artifact_paths"],
        "input_schema": entry["input_schema"],
        "extra_actions": entry["extra_actions"],
        "children": [
            {
                "source_id": child["source_id"],
                "display_name": child["display_name"],
                "kind": child["kind"],
                "repo_owner": child["repo_owner"],
                "artifacts": child["artifact_paths"],
            }
            for child in children
        ],
    }


def build_catalog_payload(repo_root: Path, fundman_root: Path) -> dict[str, Any]:
    registry = build_registry(repo_root=repo_root, fundman_root=fundman_root)
    families = [_family_catalog_entry(registry[source_id], registry) for source_id in FAMILY_ORDER]
    advanced_tools = [_family_catalog_entry(registry[source_id], registry) for source_id in ADVANCED_TOOL_ORDER]
    return {
        "generated_at": _now_hkt().isoformat(timespec="seconds"),
        "families": families,
        "advanced_tools": advanced_tools,
    }


def build_status_payload(
    repo_root: Path,
    fundman_root: Path,
    now_iso: str | None = None,
    jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = build_registry(repo_root=repo_root, fundman_root=fundman_root)
    now = _now_hkt(now_iso)
    persisted_jobs = load_ops_state(repo_root).get("jobs", {}) if jobs is None else jobs

    families: list[dict[str, Any]] = []
    for family_id in FAMILY_ORDER:
        entry = registry[family_id]
        children = [
            _child_payload(child_entry, repo_root, fundman_root, now)
            for child_entry in registry.values()
            if child_entry["family_id"] == family_id and child_entry["source_id"] != family_id
        ]
        children.sort(key=lambda item: item["display_name"].lower())
        auth = _status_from_stamp(entry.get("session_service"), repo_root, now)
        family_freshness = _evaluate_freshness(entry, repo_root, fundman_root, now)
        job = persisted_jobs.get(family_id)
        families.append(
            {
                "source_id": family_id,
                "display_name": entry["display_name"],
                "family_id": family_id,
                "kind": entry["kind"],
                "repo_owner": entry["repo_owner"],
                "status": _aggregate_family_status(children, family_freshness, auth, job),
                "auth": auth,
                "job": job,
                "artifacts": entry["artifact_paths"],
                "freshness": family_freshness,
                "action_kind": entry["action_kind"],
                "input_schema": entry["input_schema"],
                "extra_actions": entry["extra_actions"],
                "children": children,
            }
        )

    advanced_tools: list[dict[str, Any]] = []
    for source_id in ADVANCED_TOOL_ORDER:
        entry = registry[source_id]
        job = persisted_jobs.get(source_id)
        status = _job_to_status(job) or "missing"
        advanced_tools.append(
            {
                "source_id": source_id,
                "display_name": entry["display_name"],
                "family_id": entry["family_id"],
                "kind": entry["kind"],
                "repo_owner": entry["repo_owner"],
                "status": status,
                "job": job,
                "artifacts": entry["artifact_paths"],
                "action_kind": entry["action_kind"],
                "input_schema": entry["input_schema"],
                "extra_actions": entry["extra_actions"],
            }
        )

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "families": families,
        "advanced_tools": advanced_tools,
    }


def _python_executable(python_exe: str | None = None) -> str:
    return python_exe or sys.executable or "python"


def build_action_request(
    source_id: str,
    params: dict[str, Any] | None = None,
    *,
    repo_root: Path,
    fundman_root: Path,
    python_exe: str | None = None,
) -> dict[str, Any]:
    registry = build_registry(repo_root=repo_root, fundman_root=fundman_root)
    if source_id not in registry:
        raise KeyError(source_id)

    entry = registry[source_id]
    request_params = dict(params or {})
    action_name = request_params.pop("action_name", None)

    python_cmd = _python_executable(python_exe)
    command_parts = entry.get("action_command")

    if action_name:
        for extra_action in entry.get("extra_actions", []):
            if extra_action.get("action_name") == action_name:
                command_parts = extra_action.get("action_command")
                break

    if entry["repo_owner"] == "fundman-jarvis" or entry["kind"] == "parameterized_tool":
        command = [
            python_cmd,
            "tools/external_scraper_bridge.py",
            "--source-id",
            source_id,
            "--fundman-root",
            str(fundman_root),
        ]
        if request_params:
            command.extend(
                [
                    "--params-json",
                    json.dumps(request_params, ensure_ascii=False, separators=(",", ":")),
                ]
            )
        return {
            "source_id": source_id,
            "cwd": str(repo_root),
            "command": command,
            "params": request_params,
        }

    if not command_parts:
        raise ValueError(f"No action command configured for {source_id}")

    return {
        "source_id": source_id,
        "cwd": str(repo_root),
        "command": [python_cmd, *command_parts],
        "params": request_params,
    }
