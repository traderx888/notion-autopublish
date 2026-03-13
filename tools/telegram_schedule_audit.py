from __future__ import annotations

import argparse
import ast
import html
import json
import re
import subprocess
import sys
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

try:
    from tools.telegram_hub import load_telegram_credentials, send_messages, split_message
except ImportError:  # pragma: no cover - script execution fallback
    from telegram_hub import load_telegram_credentials, send_messages, split_message


DEFAULT_ROOT = Path(r"C:\Users\User\Documents\GitHub")
DEFAULT_REPOS = ("All-in-one", "fundman-jarvis", "notion-autopublish")
DEFAULT_OUTPUT_REL = Path("outputs") / "ops" / "telegram_schedule_audit_latest.json"
FLOW_DOC_REL = Path("docs") / "telegram_schedule_audit_flow.md"
FLOW_SVG_REL = Path("docs") / "telegram_schedule_audit_flow.svg"
FLOW_EXCALIDRAW_REL = Path("docs") / "telegram_schedule_audit_flow.excalidraw"
HK_TZ = ZoneInfo("Asia/Hong_Kong")
CONTROL_FILE_REL = Path("workflow") / "cross_repo_tasks.yaml"
KNOWN_SCHEDULER_FIELDS = (
    "Repeat: Until: Time:",
    "Repeat: Every:",
    "Task To Run:",
    "Schedule Type:",
    "Start Time:",
    "Start Date:",
    "TaskName:",
    "Start In:",
    "Comment:",
    "Status:",
    "Days:",
    "Months:",
)
WRAPPER_TASKS = {
    "run_deepvue_dashboard.bat": {
        "task_key": "deepvue_dashboard",
        "schedule_text": "Mon-Fri 15:30 HKT",
        "telegram_related": True,
        "command": "run_deepvue_dashboard.bat",
    },
    "run_sector_screenshots.bat": {
        "task_key": "sector_heatmap",
        "schedule_text": "Mon-Fri 15:30 HKT",
        "telegram_related": True,
        "command": "run_sector_screenshots.bat",
    },
    "run_light.bat": {
        "task_key": "jarvis_light",
        "schedule_text": "",
        "telegram_related": True,
        "command": "run_light.bat",
    },
    "run_full.bat": {
        "task_key": "jarvis_full",
        "schedule_text": "",
        "telegram_related": True,
        "command": "run_full.bat",
    },
    "start_ops_listener.bat": {
        "task_key": "fundman_telegram_ops_listener",
        "schedule_text": "",
        "telegram_related": True,
        "command": "start_ops_listener.bat",
    },
    "run_schedule_audit.bat": {
        "task_key": "schedule_audit",
        "schedule_text": "Mon-Fri 06:15 HKT",
        "telegram_related": True,
        "command": "run_schedule_audit.bat",
    },
    "run_cbbc_tracker.bat": {
        "task_key": "jarvis_cbbc_tracker_am",
        "schedule_text": "Daily 09:00 HKT",
        "telegram_related": True,
        "command": "run_cbbc_tracker.bat",
    },
    "run_crypto_news.bat": {
        "task_key": "crypto_news_daily",
        "schedule_text": "Daily 11:00 HKT",
        "telegram_related": True,
        "command": "run_crypto_news.bat",
    },
    "run_portfolio_digest.bat": {
        "task_key": "portfolio_digest",
        "schedule_text": "",
        "telegram_related": True,
        "command": "run_portfolio_digest.bat",
    },
}
SHARED_WRAPPER_INSTANCES = (
    {
        "file_name": "run_excel_sync.bat",
        "task_key": "jarvis_excel_sync_am",
        "schedule_text": "Daily 10:30 HKT",
        "command": "run_excel_sync.bat",
    },
    {
        "file_name": "run_excel_sync.bat",
        "task_key": "jarvis_excel_sync_pm",
        "schedule_text": "Daily 21:00 HKT",
        "command": "run_excel_sync.bat",
    },
    {
        "file_name": "run_portfolio_commentary.bat",
        "task_key": "jarvis_portfolio_am",
        "schedule_text": "Daily 09:00 HKT",
        "command": "run_portfolio_commentary.bat",
    },
    {
        "file_name": "run_portfolio_commentary.bat",
        "task_key": "jarvis_portfolio_pm",
        "schedule_text": "Daily 20:30 HKT",
        "command": "run_portfolio_commentary.bat",
    },
    {
        "file_name": "run_options_expiry.bat",
        "task_key": "options_earnings_2100",
        "schedule_text": "Daily 21:00 HKT",
        "command": "run_options_expiry.bat",
    },
    {
        "file_name": "run_options_expiry.bat",
        "task_key": "options_earnings_2330",
        "schedule_text": "Daily 23:30 HKT",
        "command": "run_options_expiry.bat",
    },
)
ARGUMENT_WRAPPER_INSTANCES = (
    {
        "file_name": "run_crypto_etf_flows.bat",
        "task_key": "crypto_etf_flow_am",
        "schedule_text": "Daily 09:00 HKT",
        "telegram_related": True,
        "command": "run_crypto_etf_flows.bat morning",
    },
    {
        "file_name": "run_crypto_etf_flows.bat",
        "task_key": "crypto_etf_flow_mid",
        "schedule_text": "Daily 11:50 HKT",
        "telegram_related": True,
        "command": "run_crypto_etf_flows.bat midday",
    },
)
ISSUE_ORDER = (
    "missing_in_control",
    "missing_in_scheduler",
    "missing_in_repo",
    "schedule_mismatch",
    "enabled_mismatch",
    "orphaned_wrapper",
    "info_only_schedule",
)
LANE_ORDER = ("live_scheduler", "repo_only", "disabled")
LANE_TITLES = {
    "live_scheduler": "Live Scheduler Tasks",
    "repo_only": "Repo-defined / Not Currently Scheduled",
    "disabled": "Disabled",
}
CHART_METADATA = {
    "p_model_check": {
        "display_name": "P-model Check",
        "source_group": "P-model scraper + parser",
        "source_detail": "Pre-market PAM / P-model signal check",
        "default_time": "05:00 HKT",
        "runtime_entry": "daily_reminders.py --task pam_check",
    },
    "morning_digest": {
        "display_name": "Morning Digest",
        "source_group": "Cross-source synthesis",
        "source_detail": "Morning synthesis across core sources",
        "default_time": "07:00 HKT",
        "runtime_entry": "daily_reminders.py --task morning_digest",
    },
    "excel": {
        "display_name": "Excel Reminder",
        "source_group": "Manual reminder",
        "source_detail": "Manual Excel and data reminder",
        "default_time": "10:00 HKT",
        "runtime_entry": "daily_reminders.py --task excel",
    },
    "story_1030": {
        "display_name": "Market Storyteller",
        "source_group": "Market storyteller",
        "source_detail": "Narrative market summary from storyteller model",
        "default_time": "10:30 HKT",
        "runtime_entry": "run_daily_reminder.bat story_1030",
    },
    "southbound": {
        "display_name": "Southbound Flow",
        "source_group": "Eastmoney + screen brief",
        "source_detail": "Southbound screenshot and screen brief",
        "default_time": "15:30 HKT",
        "runtime_entry": "daily_reminders.py --task southbound",
    },
    "deepvue_dashboard": {
        "display_name": "DeepVue Dashboard",
        "source_group": "DeepVue + screen brief",
        "source_detail": "DeepVue market overview and screen brief",
        "default_time": "15:30 HKT",
        "runtime_entry": "run_deepvue_dashboard.bat",
    },
    "sector_heatmap": {
        "display_name": "Sector Heatmap",
        "source_group": "CitiWarrants screenshots",
        "source_detail": "Sector screenshot flow and heatmap capture",
        "default_time": "15:30 HKT",
        "runtime_entry": "run_sector_screenshots.bat",
    },
    "usdata": {
        "display_name": "US Data Calendar",
        "source_group": "Investing.com calendar",
        "source_detail": "Calendar screenshot and macro data table",
        "default_time": "18:30 HKT",
        "runtime_entry": "daily_reminders.py --task usdata",
    },
    "daily_synthesis": {
        "display_name": "Daily Synthesis",
        "source_group": "Cross-source synthesis",
        "source_detail": "Evening multi-source synthesis update",
        "default_time": "19:00 HKT",
        "runtime_entry": "daily_reminders.py --task daily_synthesis",
    },
    "georisk": {
        "display_name": "GeoRisk Update",
        "source_group": "Geopolitics tracker",
        "source_detail": "Geopolitics risk monitor and Telegram update",
        "default_time": "20:00 HKT",
        "runtime_entry": "daily_reminders.py --task georisk",
    },
    "evening_digest": {
        "display_name": "Evening Digest",
        "source_group": "Cross-source synthesis",
        "source_detail": "Evening synthesis across core sources",
        "default_time": "21:00 HKT",
        "runtime_entry": "daily_reminders.py --task evening_digest",
    },
    "night_digest": {
        "display_name": "Night Digest",
        "source_group": "Cross-source synthesis",
        "source_detail": "Late-night synthesis across core sources",
        "default_time": "23:30 HKT",
        "runtime_entry": "daily_reminders.py --task night_digest",
    },
    "telegram_hub_hourly": {
        "display_name": "Telegram Hub Hourly",
        "source_group": "Cross-repo digest",
        "source_detail": "Hourly cross-repo Telegram digest",
        "default_time": "16:26 HKT",
        "runtime_entry": "run_telegram_hub.bat",
    },
    "jarvis_cbbc_tracker_am": {
        "display_name": "HK CBBC Tracker (牛熊證)",
        "source_group": "HK CBBC tracker",
        "source_detail": "SG Warrants bull/bear distribution",
        "default_time": "09:00 HKT",
        "runtime_entry": "send_cbbc_tracker.py",
    },
    "crypto_etf_flow_am": {
        "display_name": "Crypto ETF Flow (AM)",
        "source_group": "Crypto ETF flow",
        "source_detail": "Pre-Market Crypto ETF cash flow summary",
        "default_time": "09:00 HKT",
        "runtime_entry": "run_crypto_etf_flows.bat morning",
    },
    "crypto_etf_flow_mid": {
        "display_name": "Crypto ETF Flow (Mid)",
        "source_group": "Crypto ETF flow",
        "source_detail": "Midday Crypto ETF cash flow update",
        "default_time": "11:50 HKT",
        "runtime_entry": "run_crypto_etf_flows.bat midday",
    },
    "crypto_news_daily": {
        "display_name": "Crypto Daily News",
        "source_group": "Crypto news",
        "source_detail": "Top 8 Chinese + English crypto headlines",
        "default_time": "11:00 HKT",
        "runtime_entry": "run_crypto_news.bat",
    },
    "jarvis_portfolio_am": {
        "display_name": "JARVIS Portfolio Commentary (AM)",
        "source_group": "Portfolio commentary",
        "source_detail": "Portfolio actions vs model signals",
        "default_time": "09:00 HKT",
        "runtime_entry": "run_portfolio_commentary.bat",
    },
    "jarvis_portfolio_pm": {
        "display_name": "JARVIS Portfolio Commentary (PM)",
        "source_group": "Portfolio commentary",
        "source_detail": "Portfolio actions vs model signals",
        "default_time": "20:30 HKT",
        "runtime_entry": "run_portfolio_commentary.bat",
    },
    "jarvis_excel_sync_am": {
        "display_name": "Jarvis Excel Sync AM",
        "source_group": "Excel sync",
        "source_detail": "Excel sync workflow",
        "default_time": "10:30 HKT",
        "runtime_entry": "run_excel_sync.bat",
    },
    "jarvis_excel_sync_pm": {
        "display_name": "Jarvis Excel Sync PM",
        "source_group": "Excel sync",
        "source_detail": "Excel sync workflow",
        "default_time": "21:00 HKT",
        "runtime_entry": "run_excel_sync.bat",
    },
    "jarvis_full": {
        "display_name": "JARVIS Full",
        "source_group": "JARVIS controller",
        "source_detail": "Full controller run",
        "default_time": "05:00 HKT",
        "runtime_entry": "run_full.bat",
    },
    "jarvis_light_0950": {
        "display_name": "JARVIS Light 09:50",
        "source_group": "JARVIS controller",
        "source_detail": "Light controller run",
        "default_time": "09:50 HKT",
        "runtime_entry": "run_light.bat",
    },
    "jarvis_light_2100": {
        "display_name": "JARVIS Light 21:00",
        "source_group": "JARVIS controller",
        "source_detail": "Light controller run",
        "default_time": "21:00 HKT",
        "runtime_entry": "run_light.bat",
    },
    "jarvis_light_2230": {
        "display_name": "JARVIS Light 22:30",
        "source_group": "JARVIS controller",
        "source_detail": "Light controller run",
        "default_time": "22:30 HKT",
        "runtime_entry": "run_light.bat",
    },
    "fundman_telegram_ops_listener": {
        "display_name": "Fundman Telegram Ops Listener",
        "source_group": "Ops support",
        "source_detail": "Telegram operations listener",
        "default_time": "00:01 HKT",
        "runtime_entry": "start_ops_listener.bat",
    },
    "schedule_audit": {
        "display_name": "Telegram Schedule Audit",
        "source_group": "Ops support",
        "source_detail": "Cross-repo Telegram schedule drift audit",
        "default_time": "06:15 HKT",
        "runtime_entry": "run_schedule_audit.bat",
    },
}

CHART_METADATA["jarvis_cbbc_tracker_am"]["display_name"] = "HK CBBC Tracker (牛熊證)"
CHART_METADATA.update(
    {
        "portfolio_digest": {
            "display_name": "JARVIS Portfolio Digest",
            "source_group": "Portfolio digest",
            "source_detail": "Consolidated portfolio monitor digest",
            "runtime_entry": "run_portfolio_digest.bat",
        },
        "options_earnings_2100": {
            "display_name": "Options & Earnings Alert (21:00)",
            "source_group": "Options + earnings reminders",
            "source_detail": "Expiring options contracts and Dash earnings reminder",
            "default_time": "21:00 HKT",
            "runtime_entry": "run_options_expiry.bat",
        },
        "options_earnings_2330": {
            "display_name": "Options & Earnings Alert (23:30)",
            "source_group": "Options + earnings reminders",
            "source_detail": "Expiring options contracts and Dash earnings reminder",
            "default_time": "23:30 HKT",
            "runtime_entry": "run_options_expiry.bat",
        },
    }
)

def extract_daily_reminder_config(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    tasks: dict[str, Any] = {}
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TASKS":
                    tasks = ast.literal_eval(node.value)
                if isinstance(target, ast.Name) and target.id == "TASK_ALIASES":
                    aliases = ast.literal_eval(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "TASKS":
                tasks = ast.literal_eval(node.value)
            if node.target.id == "TASK_ALIASES":
                aliases = ast.literal_eval(node.value)
    return tasks, aliases


def parse_scheduler_query_output(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in _split_scheduler_blocks(text):
        row = _normalize_scheduler_block(block)
        if row:
            rows.append(row)
    return sorted(rows, key=lambda row: row["task_key"])


def audit_schedule_state(
    *,
    root: Path,
    repos: Sequence[str],
    scheduler_text: str | None = None,
) -> dict[str, Any]:
    scheduler_rows = parse_scheduler_query_output(
        scheduler_text if scheduler_text is not None else _run_scheduler_query()
    )
    repo_rows = discover_repo_sources(root=root, repos=repos)
    control_rows = discover_control_sources(root=root)
    merged = merge_task_rows([*repo_rows, *control_rows, *scheduler_rows])
    summary = build_summary(merged)
    return {
        "generated_at": datetime.now(HK_TZ).isoformat(),
        "root": str(root),
        "repos": list(repos),
        "records": merged,
        "summary": summary,
    }


def build_report(*, records: Sequence[dict[str, Any]], only_issues: bool = False) -> str:
    visible = [row for row in records if row["issues"] or not only_issues]
    summary = build_summary(visible)
    lines = [
        "<b>Summary</b>",
        f"Tasks tracked: {summary['total_records']}",
        f"Tasks with issues: {summary['records_with_issues']}",
    ]
    if summary["issues_by_kind"]:
        lines.append(
            "Issue counts: "
            + ", ".join(
                f"{kind}={count}" for kind, count in sorted(summary["issues_by_kind"].items())
            )
        )
    lines.append("")
    lines.extend(_render_issue_section("Missing In Control", visible, lambda row: "missing_in_control" in row["issues"]))
    lines.append("")
    lines.extend(_render_issue_section("Missing In Scheduler", visible, lambda row: "missing_in_scheduler" in row["issues"]))
    lines.append("")
    lines.extend(
        _render_issue_section(
            "Missing In Repo",
            visible,
            lambda row: "missing_in_repo" in row["issues"] or "orphaned_wrapper" in row["issues"],
        )
    )
    lines.append("")
    lines.extend(
        _render_issue_section(
            "Schedule Mismatches",
            visible,
            lambda row: "schedule_mismatch" in row["issues"] or "enabled_mismatch" in row["issues"],
        )
    )
    lines.append("")
    lines.extend(_render_issue_section("Informational", visible, lambda row: "info_only_schedule" in row["issues"]))
    lines.append("")
    lines.append("<b>Checklist</b>")
    checklist = build_checklist(visible)
    if checklist:
        lines.extend(f"- {item}" for item in checklist)
    else:
        lines.append("- No action items.")
    return "\n".join(lines).strip()


def build_checklist(records: Sequence[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    for row in sorted(records, key=lambda item: item["task_key"]):
        task = html.escape(row["task_key"])
        for issue in row["issues"]:
            if issue == "missing_in_control":
                items.append(
                    f"Add or update control entry for <code>{task}</code> in <code>All-in-one/workflow/cross_repo_tasks.yaml</code>."
                )
            elif issue == "missing_in_scheduler":
                items.append(f"Register or restore the scheduler job for <code>{task}</code>.")
            elif issue == "missing_in_repo":
                items.append(f"Add repo source mapping for <code>{task}</code>.")
            elif issue == "schedule_mismatch":
                items.append(f"Align schedule text for <code>{task}</code> across control and scheduler.")
            elif issue == "enabled_mismatch":
                items.append(f"Align enabled state for <code>{task}</code> across control and scheduler.")
            elif issue == "orphaned_wrapper":
                items.append(f"Either schedule or remove orphaned wrapper for <code>{task}</code>.")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def build_summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    issues = Counter()
    with_issues = 0
    for row in records:
        if row["issues"]:
            with_issues += 1
            issues.update(row["issues"])
    return {
        "total_records": len(records),
        "records_with_issues": with_issues,
        "issues_by_kind": dict(sorted(issues.items())),
    }


def discover_control_sources(*, root: Path) -> list[dict[str, Any]]:
    control_path = root / DEFAULT_REPOS[0] / CONTROL_FILE_REL
    payload = _load_structured_config(control_path)
    tasks = payload.get("tasks") if isinstance(payload, dict) else {}
    if not isinstance(tasks, dict):
        return []
    rows: list[dict[str, Any]] = []
    for raw_name, config in tasks.items():
        if not isinstance(config, dict):
            continue
        task_key = normalize_task_key(raw_name)
        schedule_text = str(config.get("schedule") or _control_schedule_fallback(raw_name, config)).strip()
        rows.append(
            {
                "task_key": task_key,
                "scheduler_name": raw_name,
                "owner_repo": str(config.get("owner_repo", "")).strip(),
                "source_type": "control",
                "command": str(config.get("script", "")).strip(),
                "schedule_text": schedule_text,
                "enabled": bool(config.get("enabled", True)),
                "telegram_related": task_key != "notion_publish_daily",
                "observed_in": ["control"],
                "issues": [],
            }
        )
    return rows


def discover_repo_sources(*, root: Path, repos: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repo_name in repos:
        repo_root = root / repo_name
        if repo_name == "fundman-jarvis":
            rows.extend(_discover_fundman_sources(repo_root))
        elif repo_name == "notion-autopublish":
            rows.extend(_discover_notion_sources(repo_root))
    return rows


def merge_task_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    priorities = {"scheduler": 3, "control": 2, "repo": 1, "workflow": 1}
    for row in rows:
        task_key = row["task_key"]
        current = merged.setdefault(
            task_key,
            {
                "task_key": task_key,
                "scheduler_name": "",
                "owner_repo": "",
                "source_type": row["source_type"],
                "command": "",
                "schedule_text": "",
                "enabled": bool(row.get("enabled", True)),
                "telegram_related": False,
                "observed_in": [],
                "issues": [],
                "_source_map": {},
                "_source_priorities": {},
            },
        )
        source_type = row["source_type"]
        current["_source_map"][source_type] = row
        if row.get("source_kind") == "wrapper":
            current["_source_map"][f"{source_type}:wrapper"] = row
        current["telegram_related"] = current["telegram_related"] or bool(row.get("telegram_related"))
        if source_type not in current["observed_in"]:
            current["observed_in"].append(source_type)
        if source_type == "scheduler" and row.get("scheduler_name"):
            current["scheduler_name"] = row["scheduler_name"]
        if row.get("owner_repo") and not current["owner_repo"]:
            current["owner_repo"] = row["owner_repo"]
        priority = priorities.get(source_type, 0)
        for field in ("command", "schedule_text", "source_type"):
            if row.get(field) and priority >= current["_source_priorities"].get(field, -1):
                current[field] = row[field]
                current["_source_priorities"][field] = priority
        if "control" in current["_source_map"]:
            current["enabled"] = bool(current["_source_map"]["control"].get("enabled", True))
        elif "scheduler" in current["_source_map"]:
            current["enabled"] = bool(current["_source_map"]["scheduler"].get("enabled", True))
        else:
            current["enabled"] = bool(row.get("enabled", True))

    for row in merged.values():
        row["issues"] = _classify_row(row)
        row.update(_build_chart_metadata(row))
        row["observed_in"].sort()
        row.pop("_source_priorities", None)
    result = sorted(merged.values(), key=lambda item: item["task_key"])
    for row in result:
        row.pop("_source_map", None)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit cross-repo Telegram schedule drift")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Root folder containing the core repos")
    parser.add_argument(
        "--repos",
        nargs="+",
        default=list(DEFAULT_REPOS),
        help="Repo names to audit under the root directory",
    )
    parser.add_argument("--send", action="store_true", help="Send the rendered report to Telegram")
    parser.add_argument("--only-issues", action="store_true", help="Hide records without issues in the report")
    parser.add_argument("--json-out", type=Path, default=None, help="Override JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    result = audit_schedule_state(root=root, repos=args.repos)
    report = build_report(records=result["records"], only_issues=args.only_issues)
    json_out = _resolve_json_output(root=root, explicit=args.json_out)
    write_json_payload(json_out, result)
    write_flowchart_artifacts(root=root, records=result["records"])
    print(f"JSON report written to {json_out}")
    print("=" * 56)
    for chunk in split_message(report, max_length=3900):
        print(chunk)
        print("=" * 56)
    if args.send:
        token, chat_id = load_telegram_credentials()
        send_messages(
            bot_token=token,
            chat_id=chat_id,
            messages=split_message(report, max_length=3900),
        )
        print("Telegram delivery: sent")
    else:
        print("Telegram delivery: skipped (--send not set)")
    return 0


def write_json_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _discover_fundman_sources(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tasks_path = repo_root / "daily_reminders.py"
    if tasks_path.exists():
        tasks, aliases = extract_daily_reminder_config(tasks_path)
        alias_targets = set(aliases.values())
        for name, config in sorted(tasks.items()):
            rows.append(
                {
                    "task_key": normalize_task_key(name),
                    "scheduler_name": "",
                    "owner_repo": "fundman-jarvis",
                    "source_type": "repo",
                    "command": f"python daily_reminders.py --task {name}",
                    "schedule_text": _task_schedule_text(config),
                    "enabled": True,
                    "telegram_related": True,
                    "observed_in": ["repo"],
                    "issues": [],
                    "source_kind": "daily_reminders",
                }
            )
        for alias, target in aliases.items():
            rows.append(
                {
                    "task_key": normalize_task_key(alias),
                    "scheduler_name": "",
                    "owner_repo": "fundman-jarvis",
                    "source_type": "repo",
                    "command": f"alias:{alias}->{target}",
                    "schedule_text": "",
                    "enabled": True,
                    "telegram_related": True,
                    "observed_in": ["repo"],
                    "issues": [],
                    "source_kind": "alias",
                }
            )
        for target in alias_targets:
            if not any(row["task_key"] == normalize_task_key(target) for row in rows):
                rows.append(
                    {
                        "task_key": normalize_task_key(target),
                        "scheduler_name": "",
                        "owner_repo": "fundman-jarvis",
                        "source_type": "repo",
                        "command": f"alias-target:{target}",
                        "schedule_text": "",
                        "enabled": True,
                        "telegram_related": True,
                        "observed_in": ["repo"],
                        "issues": [],
                        "source_kind": "alias",
                    }
                )

    for file_name, config in WRAPPER_TASKS.items():
        wrapper_path = repo_root / file_name
        if not wrapper_path.exists():
            continue
        rows.append(
            {
                "task_key": config["task_key"],
                "scheduler_name": "",
                "owner_repo": "fundman-jarvis",
                "source_type": "repo",
                "command": config.get("command", file_name),
                "schedule_text": config["schedule_text"],
                "enabled": True,
                "telegram_related": config["telegram_related"],
                "observed_in": ["repo"],
                "issues": [],
                "source_kind": "wrapper",
            }
        )

    for config in SHARED_WRAPPER_INSTANCES:
        wrapper_path = repo_root / config["file_name"]
        if not wrapper_path.exists():
            continue
        rows.append(
            {
                "task_key": config["task_key"],
                "scheduler_name": "",
                "owner_repo": "fundman-jarvis",
                "source_type": "repo",
                "command": config["command"],
                "schedule_text": config["schedule_text"],
                "enabled": True,
                "telegram_related": True,
                "observed_in": ["repo"],
                "issues": [],
                "source_kind": "wrapper",
            }
        )

    for config in ARGUMENT_WRAPPER_INSTANCES:
        wrapper_path = repo_root / config["file_name"]
        if not wrapper_path.exists():
            continue
        rows.append(
            {
                "task_key": config["task_key"],
                "scheduler_name": "",
                "owner_repo": "fundman-jarvis",
                "source_type": "repo",
                "command": config["command"],
                "schedule_text": config["schedule_text"],
                "enabled": True,
                "telegram_related": config["telegram_related"],
                "observed_in": ["repo"],
                "issues": [],
                "source_kind": "wrapper",
            }
        )

    run_daily = repo_root / "run_daily_reminder.bat"
    if run_daily.exists():
        _ = run_daily.read_text(encoding="utf-8", errors="ignore")
    return rows


def _discover_notion_sources(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    hub_batch = repo_root / "tools" / "run_telegram_hub.bat"
    if hub_batch.exists():
        rows.append(
            {
                "task_key": "telegram_hub_hourly",
                "scheduler_name": "",
                "owner_repo": "notion-autopublish",
                "source_type": "repo",
                "command": _compact_whitespace(hub_batch.read_text(encoding="utf-8", errors="ignore")),
                "schedule_text": "Hourly",
                "enabled": True,
                "telegram_related": True,
                "observed_in": ["repo"],
                "issues": [],
                "source_kind": "wrapper",
            }
        )

    workflow = repo_root / ".github" / "workflows" / "publish.yml"
    if workflow.exists():
        cron_expr = _extract_first_cron(workflow.read_text(encoding="utf-8", errors="ignore"))
        rows.append(
            {
                "task_key": "notion_publish_daily",
                "scheduler_name": "",
                "owner_repo": "notion-autopublish",
                "source_type": "workflow",
                "command": ".github/workflows/publish.yml",
                "schedule_text": _cron_to_hkt_label(cron_expr),
                "enabled": True,
                "telegram_related": False,
                "observed_in": ["workflow"],
                "issues": [],
            }
        )
    return rows


def _split_scheduler_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                blocks.append(current)
                current = {}
            continue
        for prefix in KNOWN_SCHEDULER_FIELDS:
            if line.startswith(prefix):
                current[prefix[:-1]] = line[len(prefix) :].strip()
                break
    if current:
        blocks.append(current)
    return blocks


def _normalize_scheduler_block(block: dict[str, str]) -> dict[str, Any] | None:
    task_name = block.get("TaskName", "").lstrip("\\").strip()
    if not task_name:
        return None
    command = _compact_whitespace(block.get("Task To Run", ""))
    start_in = block.get("Start In", "")
    owner_repo = _owner_repo_from_text(" ".join([task_name, command, start_in]))
    task_key = normalize_task_key(task_name, command=command)
    if not _is_relevant_scheduler_task(task_name=task_name, command=command, owner_repo=owner_repo, task_key=task_key):
        return None
    return {
        "task_key": task_key,
        "scheduler_name": task_name,
        "owner_repo": owner_repo,
        "source_type": "scheduler",
        "command": command,
        "schedule_text": _summarize_schedule(block),
        "enabled": block.get("Status", "").strip().lower() != "disabled",
        "telegram_related": task_key != "notion_publish_daily",
        "observed_in": ["scheduler"],
        "issues": [],
    }


def _classify_row(row: dict[str, Any]) -> list[str]:
    source_map: dict[str, Any] = row.get("_source_map", {})
    issues: list[str] = []
    if "scheduler" in source_map and "control" not in source_map and row["telegram_related"]:
        issues.append("missing_in_control")
    if (
        "control" in source_map
        and source_map["control"].get("enabled", True)
        and "scheduler" not in source_map
        and row["telegram_related"]
    ):
        issues.append("missing_in_scheduler")
    if ("control" in source_map or "scheduler" in source_map) and not (
        "repo" in source_map or "workflow" in source_map
    ):
        issues.append("missing_in_repo")
    if "control" in source_map and "scheduler" in source_map:
        control_schedule = normalize_schedule_text(source_map["control"].get("schedule_text", ""))
        scheduler_schedule = normalize_schedule_text(source_map["scheduler"].get("schedule_text", ""))
        if control_schedule and scheduler_schedule and control_schedule != scheduler_schedule:
            issues.append("schedule_mismatch")
        if bool(source_map["control"].get("enabled", True)) != bool(source_map["scheduler"].get("enabled", True)):
            issues.append("enabled_mismatch")
    if (
        "repo:wrapper" in source_map
        and "control" not in source_map
        and "scheduler" not in source_map
    ):
        issues.append("orphaned_wrapper")
    if "workflow" in source_map and not row["telegram_related"]:
        issues.append("info_only_schedule")
    return [issue for issue in ISSUE_ORDER if issue in issues]


def _render_issue_section(
    title: str,
    records: Sequence[dict[str, Any]],
    predicate,
) -> list[str]:
    lines = [f"<b>{title}</b>"]
    matches = [row for row in records if predicate(row)]
    if not matches:
        lines.append("- None.")
        return lines
    for row in matches:
        issues = ", ".join(row["issues"])
        owner = row["owner_repo"] or "unknown"
        schedule = row["schedule_text"] or "n/a"
        scheduler_name = f" [{html.escape(row['scheduler_name'])}]" if row["scheduler_name"] else ""
        lines.append(
            f"- <code>{html.escape(row['task_key'])}</code>{scheduler_name} | repo={html.escape(owner)} | "
            f"schedule={html.escape(schedule)} | issues={html.escape(issues)}"
        )
    return lines


def _build_chart_metadata(row: dict[str, Any]) -> dict[str, Any]:
    source_map: dict[str, Any] = row.get("_source_map", {})
    meta = CHART_METADATA.get(row["task_key"], {})
    lane = _derive_lane(source_map)
    return {
        "display_name": meta.get("display_name") or _default_display_name(row["task_key"], row.get("scheduler_name", "")),
        "lane": lane,
        "source_group": meta.get("source_group") or _default_source_group(row["task_key"]),
        "source_detail": meta.get("source_detail") or _default_source_detail(row),
        "time_slots": _resolve_time_slots(row=row, source_map=source_map, meta=meta),
        "runtime_entry": meta.get("runtime_entry") or _summarize_runtime_entry(row),
        "state_reason": _state_reason(lane=lane, source_map=source_map),
    }


def render_flow_markdown(records: Sequence[dict[str, Any]]) -> str:
    visible = _chart_records(records)
    lines = [
        "# Telegram Alert Map",
        "",
        "This map is generated from normalized Telegram schedule records.",
        "",
        "## Flow Chart",
        "",
        "```mermaid",
        *render_flow_mermaid(records=visible),
        "```",
        "",
        "## Why items were missing before",
        "",
        "- The previous map was a manual summary rather than a full generated inventory.",
        "- The audit engine did not model every sender wrapper, especially `Crypto ETF Flow (AM)` and `Crypto ETF Flow (Mid)`.",
        "- Live scheduler state and repo-defined sender inventory were mixed together without explicit lane separation, which made `HK CBBC Tracker (牛熊證)` easy to drop from the visual.",
        "",
    ]
    for lane in LANE_ORDER:
        lane_rows = [row for row in visible if row["lane"] == lane]
        lines.append(f"## {LANE_TITLES[lane]}")
        lines.append("")
        if not lane_rows:
            lines.append("- None.")
            lines.append("")
            continue
        for row in lane_rows:
            time_text = ", ".join(row.get("time_slots", [])) or "n/a"
            lines.append(
                f"- `{time_text}` | **{row['display_name']}** | {row['source_detail']} | `{row['runtime_entry']}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Inventory",
            "",
            "| State | Time (HKT) | Display Name | Task Key | Source / Model | Runtime Path | Evidence |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in visible:
        lines.append(
            "| "
            + " | ".join(
                [
                    _state_label(row["lane"]),
                    html.escape(_time_text(row)),
                    html.escape(row["display_name"]),
                    f"`{row['task_key']}`",
                    html.escape(row["source_detail"]),
                    f"`{row['runtime_entry']}`",
                    _evidence_label(row),
                ]
            )
            + " |"
        )
    return "\n".join(lines).strip() + "\n"


def render_flow_mermaid(*, records: Sequence[dict[str, Any]]) -> list[str]:
    lines = ["flowchart LR", '    TG["Telegram Chat"]']
    for lane in LANE_ORDER:
        lane_rows = [row for row in records if row["lane"] == lane]
        if not lane_rows:
            continue
        lines.append(f'    subgraph {lane.upper()}["{LANE_TITLES[lane]}"]')
        for row in lane_rows:
            node_id = _node_id(row["task_key"])
            label = _mermaid_label(
                "\n".join(
                    part
                    for part in [
                        row["display_name"],
                        _time_text(row),
                        row["source_detail"],
                    ]
                    if part
                )
            )
            lines.append(f'        {node_id}["{label}"]')
        lines.append("    end")
    for row in records:
        node_id = _node_id(row["task_key"])
        connector = "-.->" if row["lane"] == "disabled" else "-->"
        lines.append(f"    {node_id} {connector} TG")
    return lines


def render_flow_svg(records: Sequence[dict[str, Any]]) -> str:
    visible = _chart_records(records)
    layout = _layout_chart_cards(visible)
    total_height = layout["height"]
    tg_y = max(180.0, total_height / 2 - 80.0)
    lane_bg = {"live_scheduler": "#e7f5ff", "repo_only": "#fff9db", "disabled": "#f1f3f5"}
    lane_stroke = {"live_scheduler": "#74c0fc", "repo_only": "#fcc419", "disabled": "#adb5bd"}
    lane_dash = {"live_scheduler": "", "repo_only": "", "disabled": ' stroke-dasharray="8 6"'}
    card_fill = {"live_scheduler": "#d0ebff", "repo_only": "#fff3bf", "disabled": "#f1f3f5"}
    card_stroke = {"live_scheduler": "#1c7ed6", "repo_only": "#f08c00", "disabled": "#868e96"}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="{int(total_height)}" viewBox="0 0 1500 {int(total_height)}">',
        "  <defs>",
        '    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#495057"/>',
        "    </marker>",
        "    <style>",
        "      .title { font: 700 30px sans-serif; fill: #1e1e1e; }",
        "      .subtitle { font: 16px sans-serif; fill: #495057; }",
        "      .lane { font: 700 18px sans-serif; fill: #1e1e1e; }",
        "      .box-title { font: 700 16px sans-serif; fill: #1e1e1e; }",
        "      .box-text { font: 14px sans-serif; fill: #343a40; }",
        "      .arrow { stroke: #495057; stroke-width: 2; fill: none; marker-end: url(#arrow); }",
        "      .disabled { stroke-dasharray: 8 6; }",
        "    </style>",
        "  </defs>",
        f'  <rect x="0" y="0" width="1500" height="{int(total_height)}" fill="#ffffff"/>',
        '  <text x="750" y="42" text-anchor="middle" class="title">Telegram Alert Map</text>',
        '  <text x="750" y="72" text-anchor="middle" class="subtitle">Generated from normalized records. Live and repo-only alerts are separated into lanes.</text>',
    ]

    for lane in LANE_ORDER:
        lane_rows = [row for row in layout["rows"] if row["lane"] == lane]
        if not lane_rows:
            continue
        top = min(row["y"] for row in lane_rows) - 28
        bottom = max(row["y"] + row["height"] for row in lane_rows) + 20
        parts.append(
            f'  <rect x="24" y="{int(top)}" rx="14" ry="14" width="980" height="{int(bottom - top)}" '
            f'fill="{lane_bg[lane]}" stroke="{lane_stroke[lane]}" stroke-width="2"{lane_dash[lane]}/>'
        )
        parts.append(
            f'  <text x="40" y="{int(top + 24)}" class="lane">{html.escape(LANE_TITLES[lane])}</text>'
        )
        for row in lane_rows:
            parts.append(
                f'  <rect x="{int(row["x"])}" y="{int(row["y"])}" rx="16" ry="16" width="{int(row["width"])}" '
                f'height="{int(row["height"])}" fill="{card_fill[lane]}" stroke="{card_stroke[lane]}" stroke-width="2"/>'
            )
            text_y = row["y"] + 26
            for idx, line in enumerate(row["lines"]):
                css = "box-title" if idx == 0 else "box-text"
                parts.append(
                    f'  <text x="{int(row["x"] + 18)}" y="{int(text_y + idx * 22)}" class="{css}">{html.escape(line)}</text>'
                )
            arrow_class = "arrow disabled" if lane == "disabled" else "arrow"
            start_x = row["x"] + row["width"]
            start_y = row["y"] + row["height"] / 2
            end_x = 1110
            end_y = tg_y + 80
            c1_x = start_x + 100
            c2_x = end_x - 120
            parts.append(
                f'  <path class="{arrow_class}" d="M {int(start_x)} {int(start_y)} C {int(c1_x)} {int(start_y)}, {int(c2_x)} {int(end_y)}, {int(end_x)} {int(end_y)}"/>'
            )

    parts.extend(
        [
            f'  <rect x="1110" y="{int(tg_y)}" rx="22" ry="22" width="280" height="160" fill="#fff4e6" stroke="#e67700" stroke-width="3"/>',
            f'  <text x="1250" y="{int(tg_y + 56)}" text-anchor="middle" class="box-title">Telegram Chat</text>',
            f'  <text x="1250" y="{int(tg_y + 86)}" text-anchor="middle" class="box-text">All alert paths converge here</text>',
            f'  <text x="1250" y="{int(tg_y + 110)}" text-anchor="middle" class="box-text">Lane color shows live vs repo-only vs disabled</text>',
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def render_flow_excalidraw(records: Sequence[dict[str, Any]]) -> str:
    visible = _chart_records(records)
    layout = _layout_chart_cards(visible)
    total_height = layout["height"]
    timestamp = "2026-03-12T13:30:00.000Z"
    elements: list[dict[str, Any]] = [
        {
            "id": "title",
            "type": "text",
            "x": 470,
            "y": 20,
            "width": 360,
            "height": 40,
            "strokeColor": "#1e1e1e",
            "text": "Telegram Alert Map",
            "fontSize": 30,
            "fontFamily": "1",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "version": 1,
            "syncedAt": timestamp,
            "source": "codex",
        },
        {
            "id": "subtitle",
            "type": "text",
            "x": 280,
            "y": 62,
            "width": 760,
            "height": 44,
            "strokeColor": "#495057",
            "text": "Generated from normalized records. Live scheduled alerts and repo-only senders use separate lanes.",
            "fontSize": 16,
            "fontFamily": "1",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "version": 1,
            "syncedAt": timestamp,
            "source": "codex",
        },
    ]
    lane_fill = {"live_scheduler": "#e7f5ff", "repo_only": "#fff9db", "disabled": "#f1f3f5"}
    lane_stroke = {"live_scheduler": "#74c0fc", "repo_only": "#fcc419", "disabled": "#adb5bd"}
    card_fill = {"live_scheduler": "#d0ebff", "repo_only": "#fff3bf", "disabled": "#f1f3f5"}
    card_stroke = {"live_scheduler": "#1c7ed6", "repo_only": "#f08c00", "disabled": "#868e96"}
    tg_y = max(180.0, total_height / 2 - 80.0)

    for lane in LANE_ORDER:
        lane_rows = [row for row in layout["rows"] if row["lane"] == lane]
        if not lane_rows:
            continue
        top = min(row["y"] for row in lane_rows) - 28
        bottom = max(row["y"] + row["height"] for row in lane_rows) + 20
        elements.append(
            {
                "id": f"lane-{lane}",
                "type": "rectangle",
                "x": 24,
                "y": top,
                "width": 980,
                "height": bottom - top,
                "backgroundColor": lane_fill[lane],
                "strokeColor": lane_stroke[lane],
                "strokeStyle": "dashed" if lane == "disabled" else "solid",
                "opacity": 40,
                "label": {"text": ""},
                "roundness": {"type": 3},
                "fillStyle": "solid",
                "createdAt": timestamp,
                "updatedAt": timestamp,
                "version": 1,
                "syncedAt": timestamp,
                "source": "codex",
            }
        )
        elements.append(
            {
                "id": f"lane-title-{lane}",
                "type": "text",
                "x": 40,
                "y": top + 6,
                "width": 420,
                "height": 24,
                "strokeColor": "#1e1e1e",
                "text": LANE_TITLES[lane],
                "fontSize": 18,
                "fontFamily": "1",
                "createdAt": timestamp,
                "updatedAt": timestamp,
                "version": 1,
                "syncedAt": timestamp,
                "source": "codex",
            }
        )
        for row in lane_rows:
            elements.append(
                {
                    "id": f"card-{row['task_key']}",
                    "type": "rectangle",
                    "x": row["x"],
                    "y": row["y"],
                    "width": row["width"],
                    "height": row["height"],
                    "backgroundColor": card_fill[lane],
                    "strokeColor": card_stroke[lane],
                    "strokeStyle": "dashed" if lane == "disabled" else "solid",
                    "label": {"text": "\n".join(row["lines"])},
                    "roundness": {"type": 3},
                    "fillStyle": "solid",
                    "createdAt": timestamp,
                    "updatedAt": timestamp,
                    "version": 1,
                    "syncedAt": timestamp,
                    "source": "codex",
                }
            )
            elements.append(
                {
                    "id": f"arrow-{row['task_key']}",
                    "type": "arrow",
                    "x": row["x"] + row["width"],
                    "y": row["y"] + row["height"] / 2,
                    "strokeColor": "#495057",
                    "strokeStyle": "dashed" if lane == "disabled" else "solid",
                    "label": {"text": ""},
                    "createdAt": timestamp,
                    "updatedAt": timestamp,
                    "version": 1,
                    "points": [
                        [0, 0],
                        [1110 - (row["x"] + row["width"]), tg_y + 80 - (row["y"] + row["height"] / 2)],
                    ],
                    "syncedAt": timestamp,
                    "source": "codex",
                }
            )

    elements.append(
        {
            "id": "tg-box",
            "type": "rectangle",
            "x": 1110,
            "y": tg_y,
            "width": 280,
            "height": 160,
            "backgroundColor": "#fff4e6",
            "strokeColor": "#e67700",
            "label": {"text": "Telegram Chat\nAll alert paths\nconverge here"},
            "roundness": {"type": 3},
            "fillStyle": "solid",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "version": 1,
            "syncedAt": timestamp,
            "source": "codex",
        }
    )
    return json.dumps({"success": True, "elements": elements, "count": len(elements)}, indent=2, ensure_ascii=False) + "\n"


def write_flowchart_artifacts(*, root: Path, records: Sequence[dict[str, Any]]) -> None:
    md_path = root / "notion-autopublish" / FLOW_DOC_REL
    svg_path = root / "notion-autopublish" / FLOW_SVG_REL
    excalidraw_path = root / "notion-autopublish" / FLOW_EXCALIDRAW_REL
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_flow_markdown(records), encoding="utf-8")
    svg_path.write_text(render_flow_svg(records), encoding="utf-8")
    excalidraw_path.write_text(render_flow_excalidraw(records), encoding="utf-8")


def _chart_records(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    visible = [
        row
        for row in records
        if row.get("telegram_related") and row.get("task_key") != "notion_publish_daily"
    ]
    return sorted(visible, key=_chart_sort_key)


def _chart_sort_key(row: dict[str, Any]) -> tuple[int, str, int, str]:
    lane_idx = LANE_ORDER.index(row["lane"]) if row.get("lane") in LANE_ORDER else len(LANE_ORDER)
    return (lane_idx, row.get("source_group", ""), _time_sort_value(row.get("time_slots", [])), row["display_name"])


def _layout_chart_cards(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    y = 118.0
    card_width = 430.0
    base_height = 78.0
    for lane in LANE_ORDER:
        lane_rows = [row for row in records if row["lane"] == lane]
        if not lane_rows:
            continue
        y += 28.0
        for row in lane_rows:
            lines = [row["display_name"], _time_text(row), *_wrap_text(row["source_detail"], 44)[:2]]
            height = base_height + max(0, len(lines) - 3) * 18.0
            rows.append(
                {
                    "task_key": row["task_key"],
                    "lane": lane,
                    "x": 42.0,
                    "y": y,
                    "width": card_width,
                    "height": height,
                    "lines": [line for line in lines if line],
                }
            )
            y += height + 18.0
        y += 18.0
    return {"rows": rows, "height": max(y + 80.0, 980.0)}


def _derive_lane(source_map: dict[str, Any]) -> str:
    scheduler = source_map.get("scheduler")
    if scheduler is not None:
        return "live_scheduler" if bool(scheduler.get("enabled", True)) else "disabled"
    return "repo_only"


def _resolve_time_slots(*, row: dict[str, Any], source_map: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for source_type in ("scheduler", "repo", "workflow", "control"):
        source_row = source_map.get(source_type)
        if source_row:
            candidates.extend(_extract_time_slots(source_row.get("schedule_text", "")))
    if not candidates:
        candidates.extend(_extract_time_slots(row.get("schedule_text", "")))
    if not candidates and meta.get("default_time"):
        candidates.append(meta["default_time"])
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _extract_time_slots(text: str) -> list[str]:
    return [f"{match} HKT" for match in re.findall(r"\b\d{2}:\d{2}\b", text or "")]


def _default_display_name(task_key: str, scheduler_name: str) -> str:
    if scheduler_name:
        return scheduler_name.replace("_", " ")
    return " ".join(part.upper() if part.isupper() else part.capitalize() for part in task_key.split("_"))


def _default_source_group(task_key: str) -> str:
    if task_key.startswith("jarvis_light") or task_key == "jarvis_full":
        return "JARVIS controller"
    if task_key.startswith("jarvis_portfolio"):
        return "Portfolio commentary"
    if task_key.startswith("jarvis_excel_sync"):
        return "Excel sync"
    if task_key.startswith("crypto_etf_flow"):
        return "Crypto ETF flow"
    if task_key.startswith("crypto_news"):
        return "Crypto news"
    if task_key.startswith("fundman_telegram"):
        return "Ops support"
    return "Other Telegram task"


def _default_source_detail(row: dict[str, Any]) -> str:
    return _summarize_runtime_entry(row)


def _summarize_runtime_entry(row: dict[str, Any]) -> str:
    command = _compact_whitespace(str(row.get("command", "")))
    if not command:
        return ""
    match = re.search(r'([A-Za-z]:\\[^"\s]+\.(?:py|bat|ps1|yml)|[A-Za-z0-9_./\\-]+\.(?:py|bat|ps1|yml))(.*)$', command)
    if not match:
        return command
    script = Path(match.group(1)).name
    suffix = _compact_whitespace(match.group(2).strip(" \"'"))
    return f"{script} {suffix}".strip()


def _state_reason(*, lane: str, source_map: dict[str, Any]) -> str:
    if lane == "live_scheduler":
        return "active scheduler job"
    if lane == "disabled":
        return "disabled task"
    if "repo" in source_map or "workflow" in source_map:
        return "repo sender with no scheduler match"
    return "no active scheduler match"


def _state_label(lane: str) -> str:
    return {
        "live_scheduler": "Live scheduler",
        "repo_only": "Repo only",
        "disabled": "Disabled",
    }.get(lane, lane)


def _evidence_label(row: dict[str, Any]) -> str:
    observed = set(row.get("observed_in", []))
    if row.get("lane") == "disabled":
        return "Disabled scheduler"
    if "scheduler" in observed and "repo" in observed:
        return "Scheduler + repo"
    if "scheduler" in observed:
        return "Disabled scheduler" if row.get("lane") == "disabled" else "Scheduler + repo"
    return "Repo only"


def _time_text(row: dict[str, Any]) -> str:
    return ", ".join(row.get("time_slots", [])) or "n/a"


def _time_sort_value(time_slots: Sequence[str]) -> int:
    if not time_slots:
        return 9999
    match = re.search(r"(\d{2}):(\d{2})", time_slots[0])
    if not match:
        return 9999
    return int(match.group(1)) * 60 + int(match.group(2))


def _wrap_text(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [text]


def _mermaid_label(text: str) -> str:
    return text.replace('"', "'")


def _node_id(task_key: str) -> str:
    return "N_" + re.sub(r"[^A-Za-z0-9_]", "_", task_key)


def normalize_task_key(task_name: str, command: str = "") -> str:
    raw = task_name.strip().lstrip("\\")
    lower = raw.lower()
    if raw == "TelegramHubHourly":
        return "telegram_hub_hourly"
    if raw == "Fundman-Storyteller-1030":
        return "story_1030"
    if lower.startswith("jarvis-reminder-"):
        return _canonical_task_name(raw[len("JARVIS-Reminder-") :].replace("-", "_"))
    if lower.startswith("jarvis-light-"):
        return raw.lower().replace("-", "_")
    if raw == "JARVIS-Full":
        return "jarvis_full"
    if raw == "JARVIS-Reminder-schedule-audit":
        return "schedule_audit"

    command_lower = command.lower()
    if "--task" in command_lower:
        match = re.search(r"--task\s+([A-Za-z0-9_-]+)", command, flags=re.IGNORECASE)
        if match:
            return _canonical_task_name(match.group(1))
    if "run_telegram_hub.bat" in command_lower:
        return "telegram_hub_hourly"
    if "run_crypto_etf_flows.bat" in command_lower or "send_crypto_etf_flows.py" in command_lower:
        if "midday" in command_lower or "--label midday" in command_lower:
            return "crypto_etf_flow_mid"
        return "crypto_etf_flow_am"
    if "run_crypto_news.bat" in command_lower or "send_crypto_news.py" in command_lower:
        return "crypto_news_daily"
    if "run_cbbc_tracker.bat" in command_lower or "send_cbbc_tracker.py" in command_lower:
        return "jarvis_cbbc_tracker_am"
    if "run_options_expiry.bat" in command_lower or "send_options_expiry.py" in command_lower:
        if "2330" in lower or "23:30" in command_lower:
            return "options_earnings_2330"
        return "options_earnings_2100"
    if "run_portfolio_digest.bat" in command_lower or "send_portfolio_digest.py" in command_lower:
        return "portfolio_digest"
    if "run_deepvue_dashboard.bat" in command_lower:
        return "deepvue_dashboard"
    if "run_sector_screenshots.bat" in command_lower or "send_sector_screenshots.py" in command_lower:
        return "sector_heatmap"
    if "run_light.bat" in command_lower:
        return "jarvis_light"
    if "run_full.bat" in command_lower:
        return "jarvis_full"
    if "run_portfolio_commentary.bat" in command_lower or "send_portfolio_commentary.py" in command_lower:
        if "portfolio_pm" in lower or lower.endswith("_pm"):
            return "jarvis_portfolio_pm"
        if "portfolio_am" in lower or lower.endswith("_am"):
            return "jarvis_portfolio_am"
        return "jarvis_portfolio_am"
    if "publish.yml" in command_lower:
        return "notion_publish_daily"
    return _canonical_task_name(raw.replace("-", "_"))


def normalize_schedule_text(value: str) -> str:
    return _compact_whitespace(value).strip()


def _canonical_task_name(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if key == "pam_check":
        return "p_model_check"
    return key


def _task_schedule_text(config: dict[str, Any]) -> str:
    raw = str(config.get("time", "")).strip()
    if not raw:
        return ""
    return f"Daily {raw} HKT" if raw.count(":") == 1 else raw


def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _run_scheduler_query() -> str:
    result = subprocess.run(
        ["schtasks", "/query", "/fo", "LIST", "/v"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _owner_repo_from_text(value: str) -> str:
    lower = value.lower()
    for repo in ("fundman-jarvis", "notion-autopublish", "all-in-one"):
        if repo in lower:
            return repo
    return ""


def _is_relevant_scheduler_task(*, task_name: str, command: str, owner_repo: str, task_key: str) -> bool:
    lower_name = task_name.lower()
    lower_command = command.lower()
    if task_name == "TelegramHubHourly":
        return True
    if task_key == "notion_publish_daily":
        return True
    if owner_repo in {"fundman-jarvis", "notion-autopublish"}:
        return True
    if lower_name.startswith("jarvis-") or lower_name.startswith("fundman-"):
        return True
    if "daily_reminders.py" in lower_command or "telegram_hub.py" in lower_command:
        return True
    return False


def _summarize_schedule(block: dict[str, str]) -> str:
    schedule_type = block.get("Schedule Type", "")
    start_time = _format_time(block.get("Start Time", ""))
    days = block.get("Days", "")
    repeat = block.get("Repeat: Every", "")
    lower_type = schedule_type.lower()
    if "weekly" in lower_type:
        day_text = _format_days(days)
        if day_text and start_time:
            return f"{day_text} {start_time} HKT"
    if "daily" in lower_type and start_time:
        return f"Daily {start_time} HKT"
    if "hourly" in lower_type or "hour" in repeat.lower():
        return "Hourly"
    if start_time:
        return f"{schedule_type} {start_time} HKT".strip()
    return schedule_type.strip()


def _format_days(value: str) -> str:
    mapping = {
        "MON": "Mon",
        "TUE": "Tue",
        "WED": "Wed",
        "THU": "Thu",
        "FRI": "Fri",
        "SAT": "Sat",
        "SUN": "Sun",
    }
    tokens = [mapping[token.strip()] for token in value.split(",") if token.strip() in mapping]
    if tokens == ["Mon", "Tue", "Wed", "Thu", "Fri"]:
        return "Mon-Fri"
    if tokens == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        return "Daily"
    return ", ".join(tokens)


def _format_time(value: str) -> str:
    parts = value.split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return value.strip()


def _load_structured_config(path: Path) -> dict[str, Any]:
    if not path.exists():
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


def _control_schedule_fallback(raw_name: str, config: dict[str, Any]) -> str:
    if raw_name == "TelegramHubHourly":
        return "Hourly"
    lookback = config.get("lookback_hours")
    if lookback:
        return f"Every {lookback}h"
    return ""


def _extract_first_cron(text: str) -> str:
    match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", text)
    return match.group(1).strip() if match else ""


def _cron_to_hkt_label(expr: str) -> str:
    expr = expr.strip()
    if expr == "0 1 * * *":
        return "Daily 09:00 HKT"
    match = re.fullmatch(r"(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*", expr)
    if not match:
        return f"Cron {expr}" if expr else ""
    minute = int(match.group(1))
    hour = int(match.group(2))
    utc_dt = datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)
    hkt = utc_dt.astimezone(HK_TZ)
    return f"Daily {hkt.strftime('%H:%M')} HKT"


def _resolve_json_output(*, root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve() if explicit.is_absolute() else (Path.cwd() / explicit).resolve()
    return (root / "notion-autopublish" / DEFAULT_OUTPUT_REL).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
