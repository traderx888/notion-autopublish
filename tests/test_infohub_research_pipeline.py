"""Pipeline tests for infohub_research.research using a fake InfoHubClient."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from infohub_research.bridge import InfoHubError
from infohub_research.profile_builder import build_profile_spec
from infohub_research.research import research_target, run_pipeline
from infohub_research.targets import ScreeningTarget


class FakeClient:
    def __init__(self, *, fail_sources: set[str] | None = None,
                 raise_on_activate: bool = False):
        self.fail_sources = fail_sources or set()
        self.raise_on_activate = raise_on_activate
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def activate_profile(self, spec):
        self.calls.append(("activate", spec))
        if self.raise_on_activate:
            raise InfoHubError("activate boom")
        return {
            "id": 1,
            "profile_key": "fake-" + spec["focus"].replace(" ", "_"),
            "name": spec["name"],
            "merge_action": "created_new",
        }

    def crawl_run(self, source, keywords, *, days, max_items):
        self.calls.append(("crawl", {"source": source, "keywords": keywords}))
        if source in self.fail_sources:
            raise InfoHubError(f"crawl boom for {source}")
        return {"source": source, "items": 1, "errors": []}

    def items_latest(self, source, *, limit):
        self.calls.append(("items", {"source": source, "limit": limit}))
        return [{"id": 1, "url": f"https://example/{source}", "title": f"{source} headline"}]

    def health_check(self):
        return True


def _ticker_target():
    return ScreeningTarget(
        kind="ticker",
        slug="nvda",
        keywords=["NVDA"],
        source="stockbee_ep",
        note="SUPER_SWAN",
        raw={"ticker": "NVDA", "grade": "SUPER_SWAN", "is_golden": True},
    )


def test_research_target_writes_json(tmp_path: Path):
    client = FakeClient()
    target = _ticker_target()
    payload = research_target(client, target, output_dir=tmp_path, days=2,
                              max_items_per_source=3)

    out_file = tmp_path / "nvda_news.json"
    assert out_file.exists()
    on_disk = json.loads(out_file.read_text(encoding="utf-8"))
    assert on_disk["slug"] == "nvda"
    assert on_disk["kind"] == "ticker"
    assert on_disk["infohub_profile"]["profile_key"].startswith("fake-")
    assert on_disk["total_items"] >= 1
    # Per-source items wired through.
    assert "cnbc_search" in on_disk["items_by_source"]
    assert payload["screening_signal"]["grade"] == "SUPER_SWAN"


def test_research_target_records_per_source_failures(tmp_path: Path):
    client = FakeClient(fail_sources={"reddit"})
    target = _ticker_target()
    payload = research_target(client, target, output_dir=tmp_path)
    assert "reddit" in payload["crawl_errors"]
    assert payload["items_by_source"]["reddit"] == []
    # Other sources should still have items.
    assert payload["total_items"] >= 1


def test_run_pipeline_continues_past_target_failure(tmp_path: Path):
    output_dir = tmp_path / "out"
    targets = [
        _ticker_target(),
        ScreeningTarget(
            kind="macro_keyword", slug="dcb_policy_rates",
            keywords=["fed policy"], source="dailychartbook", note="STRONG_BEAR",
            raw={},
        ),
    ]

    class FlakyClient(FakeClient):
        def __init__(self):
            super().__init__()
            self._calls = 0

        def activate_profile(self, spec):
            self._calls += 1
            if self._calls == 1:
                raise InfoHubError("first target dies")
            return super().activate_profile(spec)

    client = FlakyClient()
    summary = run_pipeline(
        scraped_dir=tmp_path,
        fundman_data_dir=None,
        outputs_dir=tmp_path,
        output_dir=output_dir,
        client=client,
        targets=targets,
    )
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["slug"] == "nvda"
    assert len(summary["results"]) == 1
    assert summary["results"][0]["slug"] == "dcb_policy_rates"

    index = json.loads((output_dir / "index.json").read_text(encoding="utf-8"))
    assert "dcb_policy_rates" in index["targets"]
    assert "nvda" not in index["targets"]


def test_build_profile_spec_picks_valid_taxonomy():
    target = _ticker_target()
    spec = build_profile_spec(target)
    assert spec["domain"] == "finance"
    assert spec["theme"] == "equities"
    assert spec["focus"] == "earnings reset"
    assert "NVDA" in spec["queries"]
    assert spec["sources"], "must select crawl sources"


def test_build_profile_spec_macro_routing():
    macro = ScreeningTarget(
        kind="macro_keyword", slug="dcb_policy_rates",
        keywords=["fed policy"], source="dailychartbook", note="STRONG_BEAR",
    )
    spec = build_profile_spec(macro)
    assert spec["theme"] == "macro"
    assert spec["focus"] == "fed cuts"


def test_build_profile_spec_event_topic():
    event = ScreeningTarget(
        kind="event_topic", slug="us_election",
        keywords=["US election"], source="polymarket",
    )
    spec = build_profile_spec(event)
    assert spec["domain"] == "finance"
    assert spec["theme"] == "macro"
    assert spec["focus"] == "inflation surprise"
