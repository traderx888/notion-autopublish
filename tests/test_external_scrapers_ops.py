from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest


def _touch_iso(path: Path, iso_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    ts = datetime.fromisoformat(iso_value).timestamp()
    os.utime(path, (ts, ts))


@pytest.fixture
def ops_module():
    import importlib

    return importlib.import_module("tools.external_scrapers_ops")


def test_registry_contains_expected_fixed_and_advanced_inventory(tmp_path: Path, ops_module):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    registry = ops_module.build_registry(repo_root=repo_root, fundman_root=fundman_root)

    required = {
        "substack",
        "substack.capitalwars",
        "substack.fomosoc",
        "substack.semianalysis",
        "substack.finallynitin",
        "substack.sysls",
        "seekingalpha",
        "seekingalpha.p_model",
        "seekingalpha.gamma_charm",
        "deepvue",
        "deepvue.market_overview",
        "deepvue.preopen",
        "macromicro",
        "institutional",
        "institutional.goldmansachs",
        "institutional.citadelsecurities",
        "institutional.morganstanley",
        "liquidity",
        "dailychartbook",
        "ciovacco",
        "notebooklm_registry",
        "telegram_fnd",
        "conchstreet_positioning",
        "wscn_live",
        "twitter_handles",
        "twitter_search",
        "threads_handles",
        "notebooklm_research",
        "infohub_events",
    }
    assert required.issubset(set(registry))
    assert registry["deepvue"]["kind"] == "auth_service"
    assert registry["deepvue.market_overview"]["freshness_rule"]["type"] == "json_timestamp_same_day"
    assert registry["substack"]["freshness_rule"]["type"] == "freshest_of"
    assert registry["substack"]["freshness_rule"]["max_hours"] == 72
    assert registry["twitter_search"]["kind"] == "parameterized_tool"


def test_build_status_payload_marks_substack_family_ok_from_stamp_and_child_artifacts(
    tmp_path: Path,
    ops_module,
):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    stamp_path = repo_root / "browser" / "sessions" / "substack" / "ceremony_stamp.json"
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(
            {
                "date": "2026-04-18",
                "login_at": "2026-04-18T09:15:00+08:00",
                "scrape_ok": True,
                "check_only": False,
                "outputs": [
                    "scraped_data/substack_authors/capitalwars_latest.txt",
                    "scraped_data/substack_authors/fomosoc_latest.txt",
                    "scraped_data/substack_authors/semianalysis_latest.txt",
                    "scraped_data/substack_authors/finallynitin_latest.txt",
                    "scraped_data/substack_authors/sysls_latest.txt",
                ],
            }
        ),
        encoding="utf-8",
    )

    for child in ("capitalwars", "fomosoc", "semianalysis", "finallynitin", "sysls"):
        path = repo_root / "scraped_data" / "substack_authors" / f"{child}_latest.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{child}\n", encoding="utf-8")
        _touch_iso(path, "2026-04-18T09:15:00+08:00")

    payload = ops_module.build_status_payload(
        repo_root=repo_root,
        fundman_root=fundman_root,
        now_iso="2026-04-18T12:00:00+08:00",
    )
    by_id = {item["source_id"]: item for item in payload["families"]}

    substack = by_id["substack"]
    assert substack["status"] == "ok"
    assert substack["auth"]["status"] == "ok"
    assert {child["source_id"] for child in substack["children"]} == {
        "substack.capitalwars",
        "substack.fomosoc",
        "substack.semianalysis",
        "substack.finallynitin",
        "substack.sysls",
    }
    assert all(child["status"] == "ok" for child in substack["children"])


def test_build_status_payload_marks_running_family_and_stale_deepvue_child(
    tmp_path: Path,
    ops_module,
):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    market = repo_root / "scraped_data" / "deepvue" / "market_overview.json"
    preopen = repo_root / "scraped_data" / "deepvue" / "preopen.json"
    market.parent.mkdir(parents=True, exist_ok=True)
    market.write_text(json.dumps({"timestamp": "2026-04-17T15:30:00+08:00"}), encoding="utf-8")
    preopen.write_text(json.dumps({"timestamp": "2026-04-18T08:40:00+08:00"}), encoding="utf-8")
    _touch_iso(market, "2026-04-17T15:31:00+08:00")
    _touch_iso(preopen, "2026-04-18T08:41:00+08:00")

    payload = ops_module.build_status_payload(
        repo_root=repo_root,
        fundman_root=fundman_root,
        now_iso="2026-04-18T12:00:00+08:00",
        jobs={
            "deepvue": {
                "source_id": "deepvue",
                "state": "running",
                "started_at": "2026-04-18T11:59:00+08:00",
            }
        },
    )
    deepvue = {item["source_id"]: item for item in payload["families"]}["deepvue"]
    children = {child["source_id"]: child for child in deepvue["children"]}

    assert deepvue["status"] == "running"
    assert children["deepvue.market_overview"]["status"] == "stale"
    assert children["deepvue.preopen"]["status"] == "ok"


def test_build_action_request_maps_local_and_bridge_actions(tmp_path: Path, ops_module):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    institutional = ops_module.build_action_request(
        "institutional",
        repo_root=repo_root,
        fundman_root=fundman_root,
        python_exe="python-test",
    )
    assert institutional["cwd"] == str(repo_root)
    assert institutional["command"] == ["python-test", "scrape_institutional.py", "--headless"]

    twitter_search = ops_module.build_action_request(
        "twitter_search",
        params={"query": "macro liquidity", "limit": 25},
        repo_root=repo_root,
        fundman_root=fundman_root,
        python_exe="python-test",
    )
    assert twitter_search["cwd"] == str(repo_root)
    assert twitter_search["command"][:3] == ["python-test", "tools/external_scraper_bridge.py", "--source-id"]
    assert "--fundman-root" in twitter_search["command"]
    assert str(fundman_root) in twitter_search["command"]
    assert "--params-json" in twitter_search["command"]
