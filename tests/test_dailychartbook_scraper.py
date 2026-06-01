import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_dailychartbook
from browser.scrapers import dailychartbook


TEST_TAXONOMY = {
    "importance_weights": {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    },
    "families": {
        "macro_growth": {
            "ticker": "DCB_MACRO_GROWTH",
            "match_keywords": ["growth", "labor", "demand", "retail sales"],
            "bull_keywords": ["growth up", "demand resilient", "labor resilient"],
            "bear_keywords": ["growth down", "demand weakening", "recession risk up", "labor weakening"],
        },
        "risk_sentiment": {
            "ticker": "DCB_RISK_SENTIMENT",
            "match_keywords": ["risk sentiment", "risk-on", "risk-off", "cross-asset stress", "volatility"],
            "bull_keywords": ["risk-on", "sentiment improving"],
            "bear_keywords": ["risk-off", "volatility rising", "stress rising"],
        },
        "breadth": {
            "ticker": "DCB_BREADTH",
            "match_keywords": ["market internals", "breadth", "participation"],
            "bull_keywords": ["breadth improving", "participation broadening"],
            "bear_keywords": ["breadth weakening", "participation narrowing"],
        },
        "special_technical": {
            "ticker": "DCB_SPECIAL_TECHNICAL",
            "match_keywords": ["special technical", "drawdown", "technical"],
            "bull_keywords": ["support holding", "oversold"],
            "bear_keywords": ["drawdown risk", "breakdown"],
        },
    },
}


def _write_packet(folder: Path, stem: str, text: str) -> Path:
    txt_path = folder / f"{stem}.txt"
    txt_path.write_text(text.strip() + "\n", encoding="utf-8")
    txt_path.with_suffix(".png").write_bytes(b"fake-png")
    return txt_path


def _packet_text(
    *,
    title: str,
    date: str,
    sequence: int,
    category: str,
    regime_signals: str,
    use_case: str,
    importance: str,
    original_text: str,
    ai_interpretation: str,
) -> str:
    return f"""
Title: {title}
Date: {date}
Sequence: {sequence}

--- Original Text ---
{original_text}

--- AI Interpretation ---
{ai_interpretation}

--- Classification ---
Category: {category}
Regime Signals: {regime_signals}
Affected Assets: SPX, XLY
Time Horizon: Tactical
Use Case: {use_case}
Importance: {importance}

--- Source ---
Source: Example Source
URL: https://example.com/{sequence}
Image URL: https://example.com/{sequence}.png
"""


def test_parse_packet_file_extracts_sections_and_image_pair(tmp_path):
    folder = tmp_path / "Dailychartbook_2026-04-02"
    folder.mkdir()
    txt_path = _write_packet(
        folder,
        "04_Retail sales",
        _packet_text(
            title="Retail sales",
            date="2026-04-02",
            sequence=4,
            category="Growth",
            regime_signals="Growth Up, Risk-On",
            use_case="Macro Regime Assessment, Sector Rotation",
            importance="High",
            original_text="US consumer spending remains resilient.",
            ai_interpretation="Retail demand remains firm and supports cyclicals.",
        ),
    )

    packet = dailychartbook.parse_packet_file(txt_path)

    assert packet["title"] == "Retail sales"
    assert packet["date"] == "2026-04-02"
    assert packet["sequence"] == 4
    assert packet["original_text"] == "US consumer spending remains resilient."
    assert packet["ai_interpretation"] == "Retail demand remains firm and supports cyclicals."
    assert packet["category"] == ["Growth"]
    assert packet["regime_signals"] == ["Growth Up", "Risk-On"]
    assert packet["use_case"] == ["Macro Regime Assessment", "Sector Rotation"]
    assert packet["importance"] == "High"
    assert packet["source"] == "Example Source"
    assert packet["url"] == "https://example.com/4"
    assert packet["image_path"] == str(txt_path.with_suffix(".png"))


def test_select_chartbook_folders_uses_calendar_window(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for folder_name in [
        "Dailychartbook_2026-02-15",
        "Dailychartbook_2026-03-10",
        "2026-04-01",
        "2026-04-03",
    ]:
        (root / folder_name).mkdir()

    selected = dailychartbook.select_chartbook_folders(root, days=30)

    assert [path.name for path in selected] == [
        "Dailychartbook_2026-03-10",
        "2026-04-01",
        "2026-04-03",
    ]


def test_classify_packet_keeps_unknown_labels_advisory_only():
    packet = {
        "packet_id": "2026-04-02-09-unknown",
        "title": "Unknown setup",
        "category": ["Mystery"],
        "regime_signals": ["Unclear Divergence"],
        "affected_assets": [],
        "time_horizon": "Tactical",
        "use_case": ["Idea Generation"],
        "importance": "Medium",
        "original_text": "Unmapped content.",
        "ai_interpretation": "This should remain packet-level only.",
    }

    classified = dailychartbook.classify_packet(packet, TEST_TAXONOMY)

    assert classified["mapped_families"] == []
    assert classified["family_contributions"] == {}


def test_classify_packet_supports_numeric_importance_scale():
    packet = {
        "packet_id": "2026-04-02-12-growth",
        "title": "Growth setup",
        "category": ["Growth"],
        "regime_signals": ["Growth Up"],
        "affected_assets": [],
        "time_horizon": "Tactical",
        "use_case": ["Macro Regime Assessment"],
        "importance": "5 / 5",
        "original_text": "Demand is improving.",
        "ai_interpretation": "Growth up and demand resilient.",
    }

    classified = dailychartbook.classify_packet(packet, TEST_TAXONOMY)

    assert classified["family_contributions"]["macro_growth"]["weight"] == 4
    assert classified["family_contributions"]["macro_growth"]["bull"] == 4


def test_build_family_scorecard_preserves_mixed_signals_and_promotes_one_sided_family():
    packets = [
        dailychartbook.classify_packet(
            {
                "packet_id": "2026-04-02-04-retail-sales",
                "title": "Retail sales",
                "category": ["Growth"],
                "regime_signals": ["Growth Up", "Risk-On"],
                "affected_assets": ["SPX"],
                "time_horizon": "Tactical",
                "use_case": ["Macro Regime Assessment"],
                "importance": "High",
                "original_text": "Consumption is firm.",
                "ai_interpretation": "Demand resilient and risk appetite improving.",
            },
            TEST_TAXONOMY,
        ),
        dailychartbook.classify_packet(
            {
                "packet_id": "2026-04-02-05-labor",
                "title": "Labor resilience",
                "category": ["Labor"],
                "regime_signals": ["Growth Up"],
                "affected_assets": ["SPX"],
                "time_horizon": "Tactical",
                "use_case": ["Macro Regime Assessment"],
                "importance": "High",
                "original_text": "Employment remains stable.",
                "ai_interpretation": "Labor resilient and cyclical risk stays supported.",
            },
            TEST_TAXONOMY,
        ),
        dailychartbook.classify_packet(
            {
                "packet_id": "2026-04-02-29-spx-drawdowns",
                "title": "SPX drawdowns",
                "category": ["Market Internals"],
                "regime_signals": ["Risk-Off", "Breadth Weakening"],
                "affected_assets": ["SPX"],
                "time_horizon": "Tactical",
                "use_case": ["Risk Management"],
                "importance": "High",
                "original_text": "Participation is deteriorating.",
                "ai_interpretation": "Breadth weakening and drawdown risk remains elevated.",
            },
            TEST_TAXONOMY,
        ),
    ]

    scorecard = dailychartbook.build_family_scorecard(packets)

    macro_growth = scorecard["families"]["macro_growth"]
    risk_sentiment = scorecard["families"]["risk_sentiment"]

    assert macro_growth["bull_score"] == 6
    assert macro_growth["bear_score"] == 0
    assert macro_growth["signal"] == "BULL"
    assert macro_growth["value"] == 1
    assert macro_growth["promoted"] is True

    assert risk_sentiment["bull_score"] == 3
    assert risk_sentiment["bear_score"] == 3
    assert risk_sentiment["signal"] == "MIXED"
    assert risk_sentiment["value"] == 0
    assert risk_sentiment["promoted"] is False
    assert risk_sentiment["top_bull_packets"][0]["packet_id"] == "2026-04-02-04-retail-sales"
    assert risk_sentiment["top_bear_packets"][0]["packet_id"] == "2026-04-02-29-spx-drawdowns"
    assert scorecard["conflict_count"] == 1


def test_run_writes_by_date_archives_and_latest_artifacts(tmp_path):
    root = tmp_path / "source"
    first_day = root / "Dailychartbook_2026-04-01"
    second_day = root / "2026-04-02"
    first_day.mkdir(parents=True)
    second_day.mkdir(parents=True)

    _write_packet(
        first_day,
        "01_Risk reset",
        _packet_text(
            title="Risk reset",
            date="2026-04-01",
            sequence=1,
            category="Risk Sentiment",
            regime_signals="Risk-Off",
            use_case="Risk Management",
            importance="High",
            original_text="Risk appetite softened.",
            ai_interpretation="Investors de-risked after a volatile session.",
        ),
    )
    _write_packet(
        second_day,
        "04_Retail sales",
        _packet_text(
            title="Retail sales",
            date="2026-04-02",
            sequence=4,
            category="Growth",
            regime_signals="Growth Up, Risk-On",
            use_case="Macro Regime Assessment, Sector Rotation",
            importance="High",
            original_text="US consumer spending remains resilient.",
            ai_interpretation="Retail demand remains firm and supports cyclicals.",
        ),
    )
    _write_packet(
        second_day,
        "05_Labor resilience",
        _packet_text(
            title="Labor resilience",
            date="2026-04-02",
            sequence=5,
            category="Labor",
            regime_signals="Growth Up",
            use_case="Macro Regime Assessment",
            importance="High",
            original_text="Employment remains stable.",
            ai_interpretation="Labor resilient and cyclical risk stays supported.",
        ),
    )

    output_dir = tmp_path / "output"
    manifest = dailychartbook.run(
        root_dir=root,
        output_dir=output_dir,
        days=30,
        taxonomy=TEST_TAXONOMY,
        generated_at="2026-04-04T09:30:00+08:00",
    )

    by_date_first = output_dir / "by_date" / "2026-04-01.json"
    by_date_second = output_dir / "by_date" / "2026-04-02.json"
    latest_scorecard = output_dir / "dailychartbook_family_scorecard_latest.json"
    latest_readings = output_dir / "dailychartbook_readings_latest.json"

    assert by_date_first.exists()
    assert by_date_second.exists()
    assert latest_scorecard.exists()
    assert latest_readings.exists()
    assert manifest["as_of_date"] == "2026-04-02"
    assert manifest["processed_dates"] == ["2026-04-01", "2026-04-02"]

    latest_scorecard_payload = json.loads(latest_scorecard.read_text(encoding="utf-8"))
    latest_readings_payload = json.loads(latest_readings.read_text(encoding="utf-8"))

    assert latest_scorecard_payload["as_of_date"] == "2026-04-02"
    assert latest_scorecard_payload["families"]["macro_growth"]["signal"] == "BULL"
    assert {item["ticker"] for item in latest_readings_payload["readings"]} >= {
        "DCB_MACRO_GROWTH",
        "DCB_CONFLICT_COUNT",
        "DCB_PACKET_COUNT",
    }


def test_scrape_dailychartbook_main_passes_root_and_days(monkeypatch, tmp_path):
    calls = {}

    def fake_run(*, root_dir, output_dir, days, date_value, taxonomy_path):
        calls["root_dir"] = root_dir
        calls["output_dir"] = output_dir
        calls["days"] = days
        calls["date_value"] = date_value
        calls["taxonomy_path"] = taxonomy_path
        return {"as_of_date": "2026-04-02", "processed_dates": ["2026-04-02"]}

    monkeypatch.setattr(scrape_dailychartbook, "run", fake_run)

    rc = scrape_dailychartbook.main(
        [
            "--root",
            str(tmp_path / "source"),
            "--output-dir",
            str(tmp_path / "output"),
            "--days",
            "7",
            "--date",
            "2026-04-02",
        ]
    )

    assert rc == 0
    assert calls["root_dir"] == tmp_path / "source"
    assert calls["output_dir"] == tmp_path / "output"
    assert calls["days"] == 7
    assert calls["date_value"] == "2026-04-02"
    assert calls["taxonomy_path"] is None
