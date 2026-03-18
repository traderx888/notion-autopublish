import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_sa_group as sa_group


def test_p_model_registry_and_aliases_cover_all_required_pages():
    assert set(sa_group.SA_GROUPS) >= {
        "gamma-charm-surface",
        "monthly-opex",
        "trade-summaries",
        "analytics-trading",
    }
    assert sa_group.GROUP_BUNDLES["p-model-core"] == [
        "trade-summaries",
        "analytics-trading",
        "gamma-charm-surface",
        "monthly-opex",
    ]
    assert sa_group.resolve_group_keys(group="pam") == sa_group.GROUP_BUNDLES["p-model-core"]
    assert sa_group.resolve_group_keys(group="gamma-charm") == ["gamma-charm-surface"]


def test_dedupe_content_blocks_normalizes_whitespace_and_preserves_order():
    deduped = sa_group.dedupe_content_blocks(
        [
            "  First   block  \n\nwith spaces ",
            "First block with spaces",
            "Second block",
            "",
        ]
    )

    assert deduped == [
        "First block with spaces",
        "Second block",
    ]


def test_write_bundle_outputs_merges_positioning_sources_and_writes_manifest(tmp_path):
    group_results = {
        "trade-summaries": {
            "url": sa_group.SA_GROUPS["trade-summaries"]["url"],
            "output_path": "",
            "screenshot_path": "debug_trade.png",
            "scraped_at": "2026-03-15T09:00:00+08:00",
            "block_count": 2,
            "char_count": 24,
            "required": True,
            "success": True,
            "error": "",
            "content": "TRADE SUMMARY BLOCK",
        },
        "analytics-trading": {
            "url": sa_group.SA_GROUPS["analytics-trading"]["url"],
            "output_path": "",
            "screenshot_path": "debug_analytics.png",
            "scraped_at": "2026-03-15T09:05:00+08:00",
            "block_count": 1,
            "char_count": 20,
            "required": True,
            "success": True,
            "error": "",
            "content": "ANALYTICS BLOCK",
        },
        "gamma-charm-surface": {
            "url": sa_group.SA_GROUPS["gamma-charm-surface"]["url"],
            "output_path": "",
            "screenshot_path": "debug_gamma.png",
            "scraped_at": "2026-03-15T09:10:00+08:00",
            "block_count": 1,
            "char_count": 12,
            "required": True,
            "success": True,
            "error": "",
            "content": "GAMMA BLOCK",
        },
        "monthly-opex": {
            "url": sa_group.SA_GROUPS["monthly-opex"]["url"],
            "output_path": "",
            "screenshot_path": "debug_monthly.png",
            "scraped_at": "2026-03-15T09:12:00+08:00",
            "block_count": 1,
            "char_count": 14,
            "required": True,
            "success": True,
            "error": "",
            "content": "MONTHLY BLOCK",
        },
    }

    manifest = sa_group.write_bundle_outputs(group_results, output_root=tmp_path)

    merged_path = tmp_path / "scraped_data" / "sa_group_predictive_models.txt"
    manifest_path = tmp_path / "scraped_data" / "sa_group_p_model_manifest.json"
    gamma_path = tmp_path / "scraped_data" / "sa_group_gamma_charm.txt"
    monthly_path = tmp_path / "scraped_data" / "sa_group_monthly_opex.txt"

    merged_text = merged_path.read_text(encoding="utf-8")
    assert "trade-summaries" in merged_text
    assert "analytics-trading" in merged_text
    assert merged_text.index("trade-summaries") < merged_text.index("analytics-trading")
    assert "GAMMA BLOCK" not in merged_text
    assert "MONTHLY BLOCK" not in merged_text
    assert gamma_path.read_text(encoding="utf-8") == "GAMMA BLOCK"
    assert monthly_path.read_text(encoding="utf-8") == "MONTHLY BLOCK"

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["bundle"] == "p-model-core"
    assert payload["groups"]["trade-summaries"]["output_path"].endswith("sa_group_trade_summaries.txt")
    assert payload["groups"]["gamma-charm-surface"]["success"] is True
    assert manifest == payload
