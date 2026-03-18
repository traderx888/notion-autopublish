import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browser.cli as browser_cli
import scrape_macromicro
from browser.scrapers import macromicro


CHART_BOOTSTRAP = """
<script>
let collection = null;
let charts = null;
let chart = {"id":7898,"name":"MM全球景氣衰退機率","slug":"mm-global-economic-recession-rate","description":"Sample description","series_last_rows":"[[[\\"2026-01-01\\",\\"39.3501\\"],[\\"2026-02-01\\",\\"38.8732\\"]]]","settings":{"valueDecimals":2,"seriesConfigs":[{"freq":"M","name_tc":"MM全球景氣衰退機率"}]}};
</script>
"""

COUNTRY_BOOTSTRAP = """
<script>
let national_id = 104;
let stat_area = {"america":{"name":"美洲","list":[{"code":"us","name":"美國"},{"code":"ca","name":"加拿大"}]},"asia":{"name":"亞洲","list":[{"code":"jp","name":"日本"}]}};
</script>
"""


def test_default_targets_cover_current_policy_links():
    assert macromicro.MacroMicroScraper.USE_CHROME_PROFILE is True
    assert "sentiment-combinations" in macromicro.DEFAULT_TARGETS
    assert (
        macromicro.DEFAULT_TARGETS["sentiment-combinations"]["url"]
        == "https://www.macromicro.me/charts/99984/Sentiment-Combinations"
    )
    assert "fear-and-greed" in macromicro.DEFAULT_TARGETS
    assert (
        macromicro.DEFAULT_TARGETS["fear-and-greed"]["url"]
        == "https://www.macromicro.me/cross-country-database/fear-and-greed"
    )
    assert macromicro.DEFAULT_TARGETS["fear-and-greed"]["analysis_domains"] == [
        "sentiment",
        "cross_sectional",
    ]
    assert "buffett-indicator" in macromicro.DEFAULT_TARGETS
    assert "pe-ratio" in macromicro.DEFAULT_TARGETS


def test_load_target_registry_supports_config_file_and_enabled_filter(tmp_path):
    config_path = tmp_path / "macromicro_targets.json"
    config_path.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "key": "macro-a",
                        "name": "Macro A",
                        "url": "https://www.macromicro.me/charts/1/example-a",
                        "page_type": "chart",
                        "analysis_domains": ["macro_cycle"],
                        "enabled": True,
                    },
                    {
                        "key": "macro-b",
                        "name": "Macro B",
                        "url": "https://www.macromicro.me/cross-country-database/example-b",
                        "page_type": "cross-country",
                        "analysis_domains": ["breadth"],
                        "enabled": False,
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    registry = macromicro.load_target_registry(config_path=config_path)

    assert set(registry) == {"macro-a"}
    assert registry["macro-a"]["analysis_domains"] == ["macro_cycle"]


def test_extract_chart_bootstrap_parses_core_metadata_and_last_rows():
    payload = macromicro.extract_chart_bootstrap(CHART_BOOTSTRAP)

    assert payload["chart_id"] == 7898
    assert payload["title"] == "MM全球景氣衰退機率"
    assert payload["slug"] == "mm-global-economic-recession-rate"
    assert payload["description"] == "Sample description"
    assert payload["value_decimals"] == 2
    assert payload["series_last_rows"][0][-1] == ["2026-02-01", "38.8732"]


def test_serialize_highcharts_series_normalizes_points():
    raw = [
        {
            "name": "MM全球景氣衰退機率",
            "data": [
                [631152000000, 47.2627],
                [633830400000, 46.029],
            ],
        }
    ]

    series = macromicro.serialize_highcharts_series(raw)

    assert series == [
        {
            "name": "MM全球景氣衰退機率",
            "points": 2,
            "first_points": [
                {"timestamp": 631152000000, "value": 47.2627},
                {"timestamp": 633830400000, "value": 46.029},
            ],
            "last_points": [
                {"timestamp": 631152000000, "value": 47.2627},
                {"timestamp": 633830400000, "value": 46.029},
            ],
        }
    ]


def test_select_preferred_network_capture_prefers_target_specific_match():
    captures = [
        {
            "url": "https://www.macromicro.me/api/v1/chart/list",
            "content_type": "application/json",
            "payload": {"items": [{"slug": "other-chart"}]},
        },
        {
            "url": "https://www.macromicro.me/api/v1/charts/7898/mm-global-economic-recession-rate",
            "content_type": "application/json",
            "payload": {"chart": {"id": 7898, "slug": "mm-global-economic-recession-rate"}},
        },
    ]

    selected = macromicro.select_preferred_network_capture(
        "global-recession-rate",
        captures,
    )

    assert selected is not None
    assert "7898" in selected["url"]


def test_select_preferred_network_capture_prefers_series_data_over_stats_for_fear_and_greed():
    captures = [
        {
            "url": "https://www.macromicro.me/cross-country-database/stats/104",
            "content_type": "application/json",
            "payload": {
                "data": [
                    {"stat_id": 46972, "name_en": "world - mm fear and greed index"},
                ],
                "important": [],
            },
        },
        {
            "url": "https://www.macromicro.me/api/cross-country-database/series/104",
            "content_type": "application/json",
            "payload": {
                "success": 1,
                "data": {
                    "46972": {
                        "info": {"id": 46972, "country": "", "name_en": "world - mm fear and greed index"},
                        "series": [["2026-03-14", 72.3]],
                    }
                },
            },
        },
    ]

    selected = macromicro.select_preferred_network_capture("fear-and-greed", captures)

    assert selected is not None
    assert selected["url"].endswith("/api/cross-country-database/series/104")


def test_extract_target_network_payload_parses_chart_series_for_global_recession_rate():
    captures = [
        {
            "url": "https://www.macromicro.me/api/v1/charts/7898/mm-global-economic-recession-rate",
            "content_type": "application/json",
            "payload": {
                "chart": {
                    "id": 7898,
                    "name": "MM Global Economic Recession Rate",
                    "slug": "mm-global-economic-recession-rate",
                    "description": "Network payload",
                    "settings": {"valueDecimals": 2},
                },
                "series": [
                    {
                        "name": "MM Global Economic Recession Rate",
                        "data": [
                            {"date": "2026-01-01", "value": 39.3501},
                            {"date": "2026-02-01", "value": 38.8732},
                        ],
                    }
                ],
            },
        }
    ]

    extracted = macromicro.extract_target_network_payload(
        "global-recession-rate",
        "chart",
        captures,
    )

    assert extracted["chart_id"] == 7898
    assert extracted["title"] == "MM Global Economic Recession Rate"
    assert extracted["series_last_rows"][0][-1] == ["2026-02-01", 38.8732]
    assert extracted["highcharts_series"][0]["last_points"][-1]["value"] == 38.8732
    assert extracted["network_capture"]["selected_url"].endswith("mm-global-economic-recession-rate")


def test_extract_target_network_payload_parses_chart_data_endpoint_shape():
    captures = [
        {
            "url": "https://www.macromicro.me/charts/data/7898",
            "content_type": "application/json;",
            "payload": {
                "success": 1,
                "data": {
                    "c:7898": {
                        "info": {
                            "id": 7898,
                            "slug": "mm-global-economic-recession-rate",
                            "name_en": "mm global recession probability",
                            "description_en": "Macro recession model",
                        },
                        "series": [["2026-01-01", 39.3501], ["2026-02-01", 38.8732]],
                    }
                },
                "showDateList": [],
            },
        }
    ]

    extracted = macromicro.extract_target_network_payload(
        "global-recession-rate",
        "chart",
        captures,
    )

    assert extracted["chart_id"] == 7898
    assert extracted["slug"] == "mm-global-economic-recession-rate"
    assert extracted["title"] == "mm global recession probability"
    assert extracted["series_last_rows"][0][-1] == ["2026-02-01", 38.8732]
    assert extracted["network_capture"]["selected_url"].endswith("/charts/data/7898")


def test_extract_target_network_payload_flattens_live_chart_series_wrapper():
    captures = [
        {
            "url": "https://www.macromicro.me/charts/data/7898",
            "content_type": "application/json;",
            "payload": {
                "success": 1,
                "data": {
                    "c:7898": {
                        "info": {
                            "id": 7898,
                            "slug": "mm-global-economic-recession-rate",
                            "name_en": "MM Global Recession Probability",
                            "description_en": "Live payload",
                        },
                        "series": [
                            [
                                ["1990-01-01", "47.2627"],
                                ["1990-02-01", "46.0290"],
                                ["1990-03-01", "43.9796"],
                            ]
                        ],
                    }
                },
            },
        }
    ]

    extracted = macromicro.extract_target_network_payload(
        "global-recession-rate",
        "chart",
        captures,
    )

    assert extracted["highcharts_series"][0]["points"] == 3
    assert extracted["highcharts_series"][0]["first_points"][0]["timestamp"] == "1990-01-01"
    assert extracted["highcharts_series"][0]["first_points"][0]["value"] == "47.2627"
    assert extracted["series_last_rows"][0][-1] == ["1990-03-01", "43.9796"]


def test_extract_target_network_payload_parses_cross_country_rows_for_fear_and_greed():
    captures = [
        {
            "url": "https://www.macromicro.me/api/v1/cross-country-database/fear-and-greed",
            "content_type": "application/json",
            "payload": {
                "data": [
                    {"code": "us", "name": "United States", "value": 72.3, "rank": 1},
                    {"code": "jp", "name": "Japan", "value": 63.1, "rank": 2},
                ]
            },
        }
    ]

    extracted = macromicro.extract_target_network_payload(
        "fear-and-greed",
        "cross-country",
        captures,
    )

    assert extracted["network_rows"][0]["name"] == "United States"
    assert extracted["network_rows"][1]["code"] == "jp"
    assert extracted["cards"][0]["title"] == "United States"
    assert "72.3" in extracted["cards"][0]["text"]
    assert extracted["network_capture"]["selected_url"].endswith("fear-and-greed")


def test_extract_target_network_payload_parses_cross_country_series_endpoint_shape():
    captures = [
        {
            "url": "https://www.macromicro.me/api/cross-country-database/series/104",
            "content_type": "application/json",
            "payload": {
                "success": 1,
                "data": {
                    "46972": {
                        "info": {
                            "id": 46972,
                            "country": "",
                            "name_en": "world - mm fear and greed index",
                        },
                        "series": [["2026-03-07", 68.0], ["2026-03-14", 72.3]],
                    },
                    "46974": {
                        "info": {
                            "id": 46974,
                            "country": "us",
                            "name_en": "us - mm fear and greed index",
                        },
                        "series": [["2026-03-07", 64.8], ["2026-03-14", 69.1]],
                    },
                },
            },
        }
    ]

    extracted = macromicro.extract_target_network_payload(
        "fear-and-greed",
        "cross-country",
        captures,
    )

    assert extracted["network_rows"][0]["name"] == "world - mm fear and greed index"
    assert extracted["network_rows"][0]["value"] == 72.3
    assert extracted["network_rows"][0]["date"] == "2026-03-14"
    assert extracted["network_rows"][1]["code"] == "us"
    assert extracted["cards"][0]["title"] == "world - mm fear and greed index"
    assert extracted["network_capture"]["selected_url"].endswith("/api/cross-country-database/series/104")


def test_extract_target_network_payload_merges_live_cross_country_metadata_from_stats_capture():
    captures = [
        {
            "url": "https://www.macromicro.me/cross-country-database/stats/104",
            "content_type": "application/json",
            "payload": {
                "data": [
                    {
                        "stat_id": 46973,
                        "country": "",
                        "name_en": "World - MM Fear and Greed Index",
                        "country_name": "World",
                    },
                    {
                        "stat_id": 46974,
                        "country": "us",
                        "name_en": "US - MM Fear and Greed Index",
                        "country_name": "United States",
                    },
                ]
            },
        },
        {
            "url": "https://www.macromicro.me/api/cross-country-database/series/104",
            "content_type": "application/json",
            "payload": {
                "success": 1,
                "data": {
                    "46973": {
                        "info": {"id": 46973, "frequency": "W", "units": "Index", "src_id": 71, "u": "idx"},
                        "series": [["2026-03-07", 68.0], ["2026-03-14", 72.3]],
                    },
                    "46974": {
                        "info": {"id": 46974, "frequency": "D", "units": "Index", "src_id": 71, "u": "idx"},
                        "series": [["2026-03-07", 64.8], ["2026-03-14", 69.1]],
                    },
                },
            },
        },
    ]

    extracted = macromicro.extract_target_network_payload(
        "fear-and-greed",
        "cross-country",
        captures,
    )

    assert extracted["network_rows"][0]["name"] == "World - MM Fear and Greed Index"
    assert extracted["network_rows"][0]["country_name"] == "World"
    assert extracted["network_rows"][0]["value"] == 72.3
    assert extracted["network_rows"][1]["code"] == "us"
    assert extracted["network_rows"][1]["country_name"] == "United States"
    assert "date: 2026-03-14" in extracted["cards"][0]["text"]


def test_extract_cross_country_bootstrap_parses_area_definitions():
    payload = macromicro.extract_cross_country_bootstrap(
        COUNTRY_BOOTSTRAP,
        page_title="MM恐懼與貪婪指數",
    )

    assert payload["title"] == "MM恐懼與貪婪指數"
    assert payload["national_id"] == 104
    assert payload["areas"]["america"]["name"] == "美洲"
    assert payload["areas"]["america"]["countries"][0] == {"code": "us", "name": "美國"}
    assert payload["areas"]["asia"]["countries"] == [{"code": "jp", "name": "日本"}]


def test_write_run_artifacts_emits_per_target_json_and_latest_manifest(tmp_path):
    results = {
        "sentiment-combinations": {
            "target_key": "sentiment-combinations",
            "title": "Sentiment Combinations",
            "url": "https://www.macromicro.me/charts/99984/Sentiment-Combinations",
            "page_type": "chart",
            "success": True,
            "screenshot": "sentiment-combinations.png",
        },
        "fear-and-greed": {
            "target_key": "fear-and-greed",
            "title": "MM恐懼與貪婪指數",
            "url": "https://www.macromicro.me/cross-country-database/fear-and-greed",
            "page_type": "cross-country",
            "success": True,
            "screenshot": "fear-and-greed.png",
        },
    }

    manifest = macromicro.write_run_artifacts(
        results,
        output_dir=tmp_path,
        generated_at="2026-03-15T12:00:00+08:00",
    )

    latest_path = tmp_path / "macromicro_latest.json"
    target_path = tmp_path / "sentiment-combinations.json"

    assert latest_path.exists()
    assert target_path.exists()
    assert json.loads(target_path.read_text(encoding="utf-8"))["title"] == "Sentiment Combinations"
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert payload["generated_at"] == "2026-03-15T12:00:00+08:00"
    assert payload["targets"]["fear-and-greed"]["page_type"] == "cross-country"
    assert manifest == payload


def test_build_network_record_payload_selects_endpoint_and_extracted_preview():
    captures = [
        {
            "url": "https://www.macromicro.me/api/v1/charts/7898/mm-global-economic-recession-rate",
            "content_type": "application/json",
            "payload": {
                "chart": {
                    "id": 7898,
                    "name": "MM Global Economic Recession Rate",
                    "slug": "mm-global-economic-recession-rate",
                },
                "series": [
                    {
                        "name": "MM Global Economic Recession Rate",
                        "data": [
                            {"date": "2026-01-01", "value": 39.3501},
                            {"date": "2026-02-01", "value": 38.8732},
                        ],
                    }
                ],
            },
        },
        {
            "url": "https://www.macromicro.me/api/v1/chart/list",
            "content_type": "application/json",
            "payload": {"items": [{"slug": "other-chart"}]},
        },
    ]

    payload = macromicro.build_network_record_payload(
        target_key="global-recession-rate",
        spec=macromicro.DEFAULT_TARGETS["global-recession-rate"],
        captures=captures,
        recorded_at="2026-03-15T12:00:00+08:00",
        final_url="https://www.macromicro.me/charts/7898/mm-global-economic-recession-rate",
        title="MM Global Economic Recession Rate",
        logged_in=True,
        screenshot_path="global-recession-rate_record.png",
    )

    assert payload["success"] is True
    assert payload["capture_count"] == 2
    assert payload["selected_endpoint"].endswith("mm-global-economic-recession-rate")
    assert payload["candidate_endpoints"][0]["top_level_keys"] == ["chart", "series"]
    assert payload["extracted_payload"]["chart_id"] == 7898
    assert payload["extracted_payload"]["network_capture"]["selected_url"].endswith(
        "mm-global-economic-recession-rate"
    )


def test_build_network_record_payload_marks_capture_success_even_when_page_login_heuristic_is_false():
    captures = [
        {
            "url": "https://www.macromicro.me/charts/data/7898",
            "content_type": "application/json;",
            "payload": {
                "success": 1,
                "data": {
                    "c:7898": {
                        "info": {"id": 7898, "slug": "mm-global-economic-recession-rate", "name_en": "mm global recession probability"},
                        "series": [["2026-02-01", 38.8732]],
                    }
                },
            },
        }
    ]

    payload = macromicro.build_network_record_payload(
        target_key="global-recession-rate",
        spec=macromicro.DEFAULT_TARGETS["global-recession-rate"],
        captures=captures,
        recorded_at="2026-03-15T12:00:00+08:00",
        final_url="https://www.macromicro.me/charts/7898/mm-global-economic-recession-rate",
        title="MM全球景氣衰退機率 | MacroMicro 財經M平方",
        logged_in=False,
        screenshot_path="global-recession-rate_record.png",
    )

    assert payload["success"] is True
    assert payload["logged_in"] is True
    assert "error" not in payload


def test_write_network_recording_artifacts_emits_manifest_and_raw_capture_files(tmp_path):
    results = {
        "fear-and-greed": {
            "target_key": "fear-and-greed",
            "target_name": "Fear And Greed",
            "url": "https://www.macromicro.me/cross-country-database/fear-and-greed",
            "page_type": "cross-country",
            "recorded_at": "2026-03-15T12:00:00+08:00",
            "success": True,
            "selected_endpoint": "https://www.macromicro.me/api/v1/cross-country-database/fear-and-greed",
            "capture_count": 1,
            "candidate_endpoints": [
                {
                    "url": "https://www.macromicro.me/api/v1/cross-country-database/fear-and-greed",
                    "content_type": "application/json",
                    "payload_type": "dict",
                    "top_level_keys": ["data"],
                    "payload_preview": "{\"data\":[]}",
                }
            ],
            "raw_captures": [
                {
                    "url": "https://www.macromicro.me/api/v1/cross-country-database/fear-and-greed",
                    "content_type": "application/json",
                    "payload": {"data": [{"code": "us", "value": 72.3}]},
                }
            ],
        }
    }

    manifest = macromicro.write_network_recording_artifacts(
        results,
        output_dir=tmp_path,
        generated_at="2026-03-15T12:05:00+08:00",
    )

    latest_path = tmp_path / "macromicro_network_recordings_latest.json"
    summary_path = tmp_path / "fear-and-greed_network_record.json"
    raw_path = tmp_path / "fear-and-greed_network_captures.json"

    assert latest_path.exists()
    assert summary_path.exists()
    assert raw_path.exists()
    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    assert manifest == latest_payload
    assert summary_payload["selected_endpoint"].endswith("fear-and-greed")
    assert "raw_captures" not in summary_payload
    assert raw_payload[0]["payload"]["data"][0]["code"] == "us"


def test_build_cookie_fetch_payload_for_fear_and_greed_uses_series_endpoint_data():
    captures = [
        {
            "url": "https://www.macromicro.me/cross-country-database/stats/104",
            "content_type": "application/json",
            "payload": {
                "data": [
                    {"stat_id": 46973, "country": "", "name_en": "World - MM Fear and Greed Index", "country_name": "World"},
                    {"stat_id": 46974, "country": "us", "name_en": "US - MM Fear and Greed Index", "country_name": "United States"},
                ]
            },
        },
        {
            "url": "https://www.macromicro.me/api/cross-country-database/series/104",
            "content_type": "application/json",
            "payload": {
                "success": 1,
                "data": {
                    "46973": {
                        "info": {"id": 46973, "frequency": "W", "units": "Index"},
                        "series": [["2026-03-07", 68.0], ["2026-03-14", 72.3]],
                    },
                    "46974": {
                        "info": {"id": 46974, "frequency": "D", "units": "Index"},
                        "series": [["2026-03-07", 64.8], ["2026-03-14", 69.1]],
                    },
                },
            },
        },
    ]

    payload = macromicro.build_cookie_fetch_payload(
        target_key="fear-and-greed",
        spec=macromicro.DEFAULT_TARGETS["fear-and-greed"],
        captures=captures,
        fetched_at="2026-03-16T00:00:00+08:00",
    )

    assert payload["success"] is True
    assert payload["fetch_mode"] == "cookie_api"
    assert payload["selected_endpoint"].endswith("/api/cross-country-database/series/104")
    assert payload["network_rows"][0]["name"] == "World - MM Fear and Greed Index"
    assert payload["network_rows"][0]["value"] == 72.3
    assert payload["network_rows"][1]["code"] == "us"


def test_build_cookie_fetch_payload_for_global_recession_rate_uses_chart_data_endpoint():
    captures = [
        {
            "url": "https://www.macromicro.me/api/view/chart/7898",
            "content_type": "application/json",
            "payload": {"success": 1, "data": {"7898": {"success": 1}}},
        },
        {
            "url": "https://www.macromicro.me/charts/data/7898",
            "content_type": "application/json;",
            "payload": {
                "success": 1,
                "data": {
                    "c:7898": {
                        "info": {
                            "id": 7898,
                            "slug": "mm-global-economic-recession-rate",
                            "name_en": "MM Global Recession Probability",
                            "description_en": "Live payload",
                        },
                        "series": [
                            [
                                ["1990-01-01", "47.2627"],
                                ["1990-02-01", "46.0290"],
                                ["1990-03-01", "43.9796"],
                            ]
                        ],
                    }
                },
            },
        },
    ]

    payload = macromicro.build_cookie_fetch_payload(
        target_key="global-recession-rate",
        spec=macromicro.DEFAULT_TARGETS["global-recession-rate"],
        captures=captures,
        fetched_at="2026-03-16T00:00:00+08:00",
    )

    assert payload["success"] is True
    assert payload["fetch_mode"] == "cookie_api"
    assert payload["selected_endpoint"].endswith("/charts/data/7898")
    assert payload["chart_id"] == 7898
    assert payload["highcharts_series"][0]["points"] == 3
    assert payload["highcharts_series"][0]["last_points"][-1]["timestamp"] == "1990-03-01"


def test_build_cookie_fetch_payload_marks_view_only_chart_response_as_incomplete():
    captures = [
        {
            "url": "https://www.macromicro.me/api/view/chart/7898",
            "content_type": "application/json",
            "payload": {"success": 1, "data": {"7898": {"success": 1}}},
        },
    ]

    payload = macromicro.build_cookie_fetch_payload(
        target_key="global-recession-rate",
        spec=macromicro.DEFAULT_TARGETS["global-recession-rate"],
        captures=captures,
        fetched_at="2026-03-16T00:00:00+08:00",
    )

    assert payload["success"] is False
    assert payload["error"] == "cookie_fetch_parse_failed"


def test_normalize_industry_overview_payload_extracts_counts_and_chart_lock_state():
    payload = macromicro.normalize_industry_overview_payload(
        {
            "hero_title": "產業決策平台",
            "hero_summary": "幫你完成產業決策。",
            "industries": [
                {"name": "人工智慧", "data_count_text": "390 條數據"},
                {"name": "半導體", "data_count_text": "578 條數據"},
            ],
            "featured_charts": [
                {
                    "category": "宏觀產業",
                    "title": "美國-S&P 500年度各板塊每股盈餘(年增率)",
                    "summary": "此為 MM Max 訂閱專屬，現在加入終身享早鳥最低價",
                },
                {
                    "category": "利潤觀測",
                    "title": "美國-各產業EPS年增率上升比例",
                    "summary": "本圖顯示美股 25 個產業群組中有多少比例大於零。",
                },
            ],
        }
    )

    assert payload["hero_title"] == "產業決策平台"
    assert payload["industries"][0]["data_count"] == 390
    assert payload["industries"][1]["data_count"] == 578
    assert payload["featured_charts"][0]["locked"] is True
    assert payload["featured_charts"][1]["locked"] is False


def test_normalize_industry_report_list_payload_marks_locked_entries_and_accessible_detail_links():
    payload = macromicro.normalize_industry_report_list_payload(
        {
            "page_title": "MM獨家報告",
            "cta_title": "成為訂閱會員享無限瀏覽",
            "reports": [
                {
                    "title": "【MM 訂閱會員快報】布局 AI 必看五大重點 QA！",
                    "date": "2026-03-12",
                    "href": "https://www.macromicro.me/subscribe?next=/mails/monthly_report",
                },
                {
                    "title": "【財經M平方】2026 年 03 月投資月報",
                    "date": "2026-02-26",
                    "href": "https://www.macromicro.me/mails/monthly_report/2026-03-monthly-outlook",
                },
            ],
        }
    )

    assert payload["report_count"] == 2
    assert payload["reports"][0]["locked"] is True
    assert payload["reports"][0]["detail_url"] is None
    assert payload["reports"][1]["locked"] is False
    assert payload["reports"][1]["detail_url"].endswith("2026-03-monthly-outlook")


def test_normalize_industry_report_list_payload_supports_industry_report_detail_urls():
    payload = macromicro.normalize_industry_report_list_payload(
        {
            "page_title": "MM Industry Report",
            "report_links": [
                {
                    "title": "Smartphone Device FAQ Mar'26",
                    "href": "https://www.macromicro.me/industry-report/smartphone-device-faq-mar-26",
                    "date": "13 Mar 2026",
                    "category": "每月FAQ",
                    "summary": "OpenAI 預計於 2026 年下半推出主打語音互動的 AI 隨身穿戴與耳機。",
                }
            ],
        }
    )

    assert payload["report_count"] == 1
    assert payload["accessible_report_count"] == 1
    assert payload["reports"][0]["locked"] is False
    assert payload["reports"][0]["detail_url"].endswith("smartphone-device-faq-mar-26")
    assert payload["reports"][0]["category"] == "每月FAQ"


def test_extract_industry_report_list_uses_report_links_fallback():
    class DummyPage:
        def evaluate(self, script):
            return {
                "page_title": "MM Industry Report",
                "cta_title": "Industry Report",
                "report_links": [
                    {
                        "title": "Smartphone Device FAQ Mar'26",
                        "href": "https://www.macromicro.me/industry-report/smartphone-device-faq-mar-26",
                        "date": "13 Mar 2026",
                        "category": "每月FAQ",
                        "sector": "手機",
                    }
                ],
            }

    scraper = macromicro.MacroMicroScraper(headless=True)
    scraper.page = DummyPage()

    payload = scraper._extract_industry_report_list()

    assert payload["report_count"] == 1
    assert payload["reports"][0]["detail_url"].endswith("smartphone-device-faq-mar-26")
    assert payload["reports"][0]["sector"] == "手機"


def test_normalize_industry_report_detail_payload_extracts_key_points_questions_and_related_reports():
    payload = macromicro.normalize_industry_report_detail_payload(
        {
            "detail_url": "https://www.macromicro.me/industry-report/smartphone-device-faq-mar-26",
            "title": "Smartphone Device FAQ Mar'26",
            "author": "Isaiah Research",
            "published_date": "2026-03-13",
            "sector": "手機",
            "report_type": "每月FAQ",
            "summary_points": [
                "OpenAI 預計於 2026 年下半推出主打語音互動的 AI 隨身穿戴與耳機。",
                "次世代高階 iPhone 將導入自研通訊晶片。",
            ],
            "question_headings": [
                "Q1： OpenAI 在創新 AI 硬體裝置的產品路線圖為何？",
                "Q2：關於下一代 iPhone 在通訊數據機與毫米波的規格配置為何？",
            ],
            "answer_previews": [
                "首先，在 AI 隨身穿戴方面，供應鏈預計相關產品將在 2026 年下半年推出。",
            ],
            "related_reports": [
                {
                    "title": "記憶體定價戰與規格脫鉤",
                    "href": "https://www.macromicro.me/industry-report/memory-pricing-war",
                }
            ],
        }
    )

    assert payload["title"] == "Smartphone Device FAQ Mar'26"
    assert payload["published_date"] == "2026-03-13"
    assert payload["report_type"] == "每月FAQ"
    assert payload["summary_points"][0].startswith("OpenAI")
    assert payload["question_headings"][0].startswith("Q1")
    assert payload["answer_previews"][0].startswith("首先")
    assert payload["related_reports"][0]["href"].endswith("memory-pricing-war")


def test_build_industry_report_research_snapshot_uses_recent_report_details():
    payload = {
        "accessible_report_count": 2,
        "report_details": [
            {
                "title": "Smartphone Device FAQ Mar'26",
                "detail_url": "https://www.macromicro.me/industry-report/smartphone-device-faq-mar-26",
                "published_date": "2026-03-13",
                "sector": "手機",
                "report_type": "每月FAQ",
                "summary_points": ["OpenAI wearable timeline"],
            },
            {
                "title": "Semiconductor FAQ Mar'26",
                "detail_url": "https://www.macromicro.me/industry-report/semiconductor-faq-mar-26",
                "published_date": "2026-03-13",
                "sector": "半導體",
                "report_type": "每月FAQ",
                "summary_points": ["Rubin output timing deferred"],
            },
        ],
    }

    snapshot = macromicro.build_industry_report_research_snapshot(payload, max_reports=2)

    assert snapshot["available"] is True
    assert snapshot["report_count"] == 2
    assert snapshot["focus_sectors"] == ["手機", "半導體"]
    assert snapshot["latest_reports"][0]["title"] == "Smartphone Device FAQ Mar'26"
    assert "OpenAI wearable timeline" in snapshot["key_points"]


def test_build_industry_report_research_snapshot_falls_back_to_answer_previews():
    payload = {
        "accessible_report_count": 1,
        "report_details": [
            {
                "title": "Memory Weekly Report",
                "detail_url": "https://www.macromicro.me/industry-report/memory-weekly-report",
                "published_date": "2026-03-11",
                "sector": "??擃?",
                "report_type": "瘥勗?",
                "summary_points": [],
                "answer_previews": ["HBM crowding-out keeps traditional memory tight into 2027."],
            }
        ],
    }

    snapshot = macromicro.build_industry_report_research_snapshot(payload, max_reports=1)

    assert snapshot["latest_reports"][0]["summary_points"] == [
        "HBM crowding-out keeps traditional memory tight into 2027."
    ]
    assert snapshot["key_points"] == ["HBM crowding-out keeps traditional memory tight into 2027."]


def test_parse_industry_report_detail_content_uses_main_lines_for_metadata_and_filters_language_links():
    payload = macromicro.parse_industry_report_detail_content(
        detail_url="https://www.macromicro.me/industry-report/smartphone-device-faq-mar-26",
        page_title="智慧型手機與裝置 FAQ Mar'26 | 產業報告 | MacroMicro 財經M平方",
        title="智慧型手機與裝置 FAQ Mar'26",
        body_lines=[
            "智慧型手機與裝置 FAQ Mar'26",
            "獨家產業報告",
            "Isaiah Research",
            "2026-03-13",
            "收藏",
            "手機",
            "每月FAQ",
            "OpenAI 預計於 2026 年下半推出主打語音互動的 AI 隨身穿戴與耳機。",
            "次世代高階 iPhone 將導入自研通訊晶片。",
            "Q1： OpenAI 在創新 AI 硬體裝置的產品路線圖為何？",
            "A1：",
            "根據我們的產業調查，OpenAI 正積極投入不同型態的穿戴式設備。",
        ],
        headings=[
            "智慧型手機與裝置 FAQ Mar'26",
            "Q1： OpenAI 在創新 AI 硬體裝置的產品路線圖為何？",
        ],
        related_reports=[
            {"title": "半導體 FAQ Mar'26", "href": "https://www.macromicro.me/industry-report/semiconductor-faq-mar-26"},
            {"title": "English", "href": "https://en.macromicro.me/industry-report/foo"},
        ],
    )

    assert payload["author"] == "Isaiah Research"
    assert payload["published_date"] == "2026-03-13"
    assert payload["sector"] == "手機"
    assert payload["report_type"] == "每月FAQ"
    assert payload["summary_points"][:2] == [
        "OpenAI 預計於 2026 年下半推出主打語音互動的 AI 隨身穿戴與耳機。",
        "次世代高階 iPhone 將導入自研通訊晶片。",
    ]
    assert payload["related_reports"] == [
        {
            "title": "半導體 FAQ Mar'26",
            "href": "https://www.macromicro.me/industry-report/semiconductor-faq-mar-26",
        }
    ]


def test_overlay_present_values_preserves_existing_fields_when_extraction_is_empty():
    merged = macromicro.overlay_present_values(
        {"title": "MM全球景氣衰退機率", "page_type": "chart"},
        {"title": None, "chart_id": 7898, "description": ""},
    )

    assert merged["title"] == "MM全球景氣衰退機率"
    assert merged["chart_id"] == 7898
    assert merged["description"] == ""


def test_is_security_verification_page_detects_cloudflare_gate():
    assert macromicro.is_security_verification_page(
        "Performing security verification Verifying..."
    ) is True
    assert macromicro.is_security_verification_page("MM全球景氣衰退機率") is False


def test_browser_cli_accepts_macromicro_scrape_service():
    parser = browser_cli.build_parser()

    args = parser.parse_args(["scrape", "macromicro", "--headless"])

    assert args.command == "scrape"
    assert args.service == "macromicro"
    assert args.headless is True


def test_scrape_macromicro_main_passes_target_and_url(monkeypatch):
    calls = {}

    class DummyScraper:
        def __init__(self, headless=False, use_chrome=None):
            calls["headless"] = headless
            calls["use_chrome"] = use_chrome

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, target_keys=None, urls=None):
            calls["target_keys"] = target_keys
            calls["urls"] = urls
            return {"targets": {}}

    monkeypatch.setattr(scrape_macromicro, "MacroMicroScraper", DummyScraper)

    rc = scrape_macromicro.main(
        [
            "--headless",
            "--target", "sentiment-combinations",
            "--url", "https://www.macromicro.me/charts/7898/mm-global-economic-recession-rate",
        ]
    )

    assert rc == 0
    assert calls["headless"] is True
    assert calls["use_chrome"] is None
    assert calls["target_keys"] == ["sentiment-combinations"]
    assert calls["urls"] == ["https://www.macromicro.me/charts/7898/mm-global-economic-recession-rate"]


def test_scrape_macromicro_main_accepts_chrome_flag(monkeypatch):
    calls = {}

    class DummyScraper:
        def __init__(self, headless=False, use_chrome=None):
            calls["headless"] = headless
            calls["use_chrome"] = use_chrome

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, target_keys=None, urls=None):
            return {"targets": {}}

    monkeypatch.setattr(scrape_macromicro, "MacroMicroScraper", DummyScraper)

    rc = scrape_macromicro.main(["--chrome"])

    assert rc == 0
    assert calls["headless"] is False
    assert calls["use_chrome"] is True


def test_scrape_macromicro_main_supports_manual_network_record_mode(monkeypatch):
    calls = {"inits": [], "record_network": 0, "run": 0}

    class DummyScraper:
        def __init__(self, headless=False, use_chrome=None):
            calls["inits"].append({"headless": headless, "use_chrome": use_chrome})

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def record_network(self, target_keys=None, urls=None):
            calls["record_network"] += 1
            calls["target_keys"] = target_keys
            calls["urls"] = urls
            return {"targets": {}}

        def run(self, target_keys=None, urls=None):
            calls["run"] += 1
            raise AssertionError("run should not be called in record mode")

    monkeypatch.setattr(scrape_macromicro, "MacroMicroScraper", DummyScraper)

    rc = scrape_macromicro.main(["--record-network", "--headless", "--target", "fear-and-greed"])

    assert rc == 0
    assert calls["record_network"] == 1
    assert calls["run"] == 0
    assert calls["inits"][0]["headless"] is False
    assert calls["target_keys"] == ["fear-and-greed"]


def test_scrape_macromicro_main_falls_back_to_headed_when_headless_session_is_blocked(monkeypatch):
    calls = {"inits": [], "runs": 0}

    class DummyScraper:
        def __init__(self, headless=False, use_chrome=None, allow_manual_login=True):
            calls["inits"].append(
                {
                    "headless": headless,
                    "use_chrome": use_chrome,
                    "allow_manual_login": allow_manual_login,
                }
            )
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, target_keys=None, urls=None):
            calls["runs"] += 1
            if self.headless:
                raise RuntimeError("MacroMicro session missing; run non-headless with --login first.")
            return {"targets": {"fear-and-greed": {"success": True}}}

    monkeypatch.setattr(scrape_macromicro, "MacroMicroScraper", DummyScraper)

    rc = scrape_macromicro.main(["--headless", "--target", "fear-and-greed"])

    assert rc == 0
    assert len(calls["inits"]) == 2
    assert calls["inits"][0]["headless"] is True
    assert calls["inits"][1]["headless"] is False
    assert calls["inits"][1]["allow_manual_login"] is False


def test_ensure_session_headed_without_manual_login_raises_when_session_missing(monkeypatch):
    scraper = macromicro.MacroMicroScraper(headless=False, allow_manual_login=False)
    calls = {"ensure_logged_in": 0}

    monkeypatch.setattr(scraper, "is_logged_in", lambda: False)

    def _fake_ensure_logged_in():
        calls["ensure_logged_in"] += 1

    monkeypatch.setattr(scraper, "ensure_logged_in", _fake_ensure_logged_in)

    try:
        scraper.ensure_session()
    except RuntimeError as exc:
        assert "session missing even in headed mode" in str(exc).lower()
    else:
        raise AssertionError("expected RuntimeError when manual login is disabled")

    assert calls["ensure_logged_in"] == 0


def test_ensure_session_raises_in_headless_mode_when_login_is_missing(monkeypatch):
    scraper = macromicro.MacroMicroScraper(headless=True)
    monkeypatch.setattr(scraper, "is_logged_in", lambda: False)

    try:
        scraper.ensure_session()
    except RuntimeError as exc:
        assert "run non-headless with --login first" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing headless session")


def test_ensure_session_uses_existing_session_in_headless_mode(monkeypatch):
    scraper = macromicro.MacroMicroScraper(headless=True)
    monkeypatch.setattr(scraper, "is_logged_in", lambda: True)

    scraper.ensure_session()


def test_ensure_session_calls_interactive_login_when_not_headless(monkeypatch):
    scraper = macromicro.MacroMicroScraper(headless=False)
    calls = {"ensure_logged_in": 0}

    def _fake_ensure_logged_in():
        calls["ensure_logged_in"] += 1

    monkeypatch.setattr(scraper, "ensure_logged_in", _fake_ensure_logged_in)

    scraper.ensure_session()

    assert calls["ensure_logged_in"] == 1


def test_goto_target_url_retries_when_login_redirect_interrupts_navigation():
    waits = []

    class DummyPage:
        def __init__(self):
            self.calls = 0

        def goto(self, url, wait_until=None):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError(
                    'Page.goto: Navigation to "https://www.macromicro.me/cross-country-database/fear-and-greed" '
                    'is interrupted by another navigation to "https://www.macromicro.me/#success"'
                )
            return None

        def wait_for_timeout(self, ms):
            waits.append(ms)
            return None

    scraper = macromicro.MacroMicroScraper(headless=False)
    scraper.page = DummyPage()

    scraper._goto_target_url("https://www.macromicro.me/cross-country-database/fear-and-greed")

    assert scraper.page.calls == 2
    assert waits == [1500]


def test_is_logged_in_rejects_security_verification_page():
    class DummyLocator:
        def __init__(self, *, count=0, text=""):
            self._count = count
            self._text = text

        def count(self):
            return self._count

        def inner_text(self, timeout=None):
            return self._text

    class DummyPage:
        def goto(self, url, wait_until=None):
            return None

        def wait_for_timeout(self, ms):
            return None

        def locator(self, selector):
            if selector == "body":
                return DummyLocator(text="Performing security verification Verifying...")
            if selector == "a[href*='/login']":
                return DummyLocator(count=0)
            raise AssertionError(f"unexpected selector: {selector}")

    scraper = macromicro.MacroMicroScraper(headless=True)
    scraper.page = DummyPage()

    assert scraper.is_logged_in() is False


def test_is_logged_in_waits_for_security_verification_to_clear(monkeypatch):
    class DummyLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector

        def count(self):
            if self.selector == "a[href*='/login']":
                return 0 if self.page.phase == "ready" else 1
            if self.selector == "main h1":
                return 1 if self.page.phase == "ready" else 0
            return 0

        def inner_text(self, timeout=None):
            if self.selector == "body":
                return (
                    "Performing security verification Verifying..."
                    if self.page.phase == "verifying"
                    else "MacroMicro paid content"
                )
            return ""

    class DummyPage:
        def __init__(self):
            self.phase = "verifying"
            self.wait_calls = 0

        def goto(self, url, wait_until=None):
            return None

        def wait_for_timeout(self, ms):
            self.wait_calls += 1
            if self.wait_calls >= 2:
                self.phase = "ready"
            return None

        def locator(self, selector):
            return DummyLocator(self, selector)

    scraper = macromicro.MacroMicroScraper(headless=True)
    scraper.page = DummyPage()

    assert scraper.is_logged_in() is True


def test_current_page_logged_in_accepts_member_menu_signals_even_with_login_link():
    class DummyLocator:
        def __init__(self, count=0, text=""):
            self._count = count
            self._text = text

        def count(self):
            return self._count

        def inner_text(self, timeout=None):
            return self._text

    class DummyPage:
        def locator(self, selector):
            counts = {
                "a[href*='/login']": 1,
                "a[href*='/logout']": 1,
                "a[href*='/user/settings']": 1,
                "a[href*='/user/mcoins']": 1,
                "body": 0,
            }
            return DummyLocator(count=counts.get(selector, 0))

    scraper = macromicro.MacroMicroScraper(headless=True)
    scraper.page = DummyPage()

    assert scraper._current_page_logged_in() is True


def test_start_reuses_existing_scraper_session_without_copying_chrome_data(monkeypatch):
    scraper = macromicro.MacroMicroScraper(headless=True)

    monkeypatch.setattr(scraper, "_has_saved_session_state", lambda: True)

    def _unexpected_running_check():
        raise AssertionError("should not inspect real Chrome when reusing existing scraper session")

    def _unexpected_copy(*args, **kwargs):
        raise AssertionError("should not copy Chrome session when scraper session already exists")

    monkeypatch.setattr("browser.base.is_chrome_running", _unexpected_running_check)
    monkeypatch.setattr("browser.base.copy_chrome_session", _unexpected_copy)

    class DummyContext:
        def __init__(self):
            self.pages = []

        def new_page(self):
            return "page"

        def close(self):
            return None

    class DummyChromium:
        def launch_persistent_context(self, **kwargs):
            return DummyContext()

    class DummyPlaywright:
        def __init__(self):
            self.chromium = DummyChromium()

        def stop(self):
            return None

    class DummySyncPlaywright:
        def start(self):
            return DummyPlaywright()

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: DummySyncPlaywright())

    page = scraper.start()

    assert page == "page"


def test_start_raises_fast_in_headless_mode_when_chrome_is_running(monkeypatch):
    scraper = macromicro.MacroMicroScraper(headless=True)
    monkeypatch.setattr(scraper, "_has_saved_session_state", lambda: False)

    monkeypatch.setattr("browser.base.is_chrome_running", lambda: True)

    try:
        scraper.start()
    except RuntimeError as exc:
        assert "Chrome must be closed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when Chrome is running in headless mode")


def test_scrape_macromicro_main_supports_login_only_mode(monkeypatch):
    calls = {"ensure_session": 0, "run": 0}

    class DummyScraper:
        def __init__(self, headless=False, use_chrome=None):
            calls["headless"] = headless
            calls["use_chrome"] = use_chrome

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ensure_session(self):
            calls["ensure_session"] += 1

        def run(self, target_keys=None, urls=None):
            calls["run"] += 1
            return {"targets": {}}

    monkeypatch.setattr(scrape_macromicro, "MacroMicroScraper", DummyScraper)

    rc = scrape_macromicro.main(["--login"])

    assert rc == 0
    assert calls["ensure_session"] == 1
    assert calls["run"] == 0


def test_scrape_macromicro_main_returns_nonzero_on_missing_session(monkeypatch, capsys):
    calls = {"inits": []}

    class DummyScraper:
        def __init__(self, headless=False, use_chrome=None, allow_manual_login=True):
            calls["inits"].append(
                {
                    "headless": headless,
                    "use_chrome": use_chrome,
                    "allow_manual_login": allow_manual_login,
                }
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, target_keys=None, urls=None):
            if calls["inits"][-1]["headless"]:
                raise RuntimeError("MacroMicro session missing; run non-headless with --login first.")
            raise RuntimeError("MacroMicro session missing even in headed mode.")

    monkeypatch.setattr(scrape_macromicro, "MacroMicroScraper", DummyScraper)

    rc = scrape_macromicro.main(["--headless"])

    captured = capsys.readouterr()
    assert rc == 2
    assert len(calls["inits"]) == 2
    assert calls["inits"][1]["allow_manual_login"] is False


def test_scrape_macromicro_main_reconfigures_stdout_for_unicode_manifest(monkeypatch):
    import io

    monkeypatch.setattr(
        scrape_macromicro,
        "_run_scrape",
        lambda **kwargs: {"generated_at": "2026-03-16T00:00:00+08:00", "title": "簡體測試"},
    )

    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp950", errors="strict")
    monkeypatch.setattr(scrape_macromicro.sys, "stdout", fake_stdout)

    rc = scrape_macromicro.main([])

    fake_stdout.flush()
    output = fake_stdout.buffer.getvalue().decode("utf-8")
    assert rc == 0
    assert "簡體測試" in output


def test_run_prefers_cookie_fetch_for_supported_target(monkeypatch, tmp_path):
    scraper = macromicro.MacroMicroScraper(headless=True)
    scraper.output_dir = tmp_path

    monkeypatch.setattr(scraper, "ensure_session", lambda: None)
    monkeypatch.setattr(
        scraper,
        "_resolve_targets",
        lambda target_keys=None, urls=None: {
            "fear-and-greed": macromicro.DEFAULT_TARGETS["fear-and-greed"],
        },
    )

    calls = {"cookie": 0, "capture": 0}

    def _cookie(target_key, spec):
        calls["cookie"] += 1
        return {"target_key": target_key, "success": True, "page_type": "cross-country"}

    def _capture(target_key, spec):
        calls["capture"] += 1
        return {"target_key": target_key, "success": True, "page_type": "cross-country"}

    monkeypatch.setattr(scraper, "_fetch_target_via_cookie_api", _cookie)
    monkeypatch.setattr(scraper, "_capture_target", _capture)

    manifest = scraper.run(target_keys=["fear-and-greed"])

    assert manifest["success_count"] == 1
    assert calls["cookie"] == 1
    assert calls["capture"] == 0


def test_run_falls_back_to_page_capture_when_cookie_fetch_raises(monkeypatch, tmp_path):
    scraper = macromicro.MacroMicroScraper(headless=True)
    scraper.output_dir = tmp_path

    monkeypatch.setattr(scraper, "ensure_session", lambda: None)
    monkeypatch.setattr(
        scraper,
        "_resolve_targets",
        lambda target_keys=None, urls=None: {
            "global-recession-rate": macromicro.DEFAULT_TARGETS["global-recession-rate"],
        },
    )

    calls = {"cookie": 0, "capture": 0}

    def _cookie(target_key, spec):
        calls["cookie"] += 1
        raise RuntimeError("cookie api failed")

    def _capture(target_key, spec):
        calls["capture"] += 1
        return {"target_key": target_key, "success": True, "page_type": "chart"}

    monkeypatch.setattr(scraper, "_fetch_target_via_cookie_api", _cookie)
    monkeypatch.setattr(scraper, "_capture_target", _capture)

    manifest = scraper.run(target_keys=["global-recession-rate"])

    assert manifest["success_count"] == 1
    assert calls["cookie"] == 1
    assert calls["capture"] == 1


def test_run_does_not_block_on_session_gate_before_fetch_attempts(monkeypatch, tmp_path):
    scraper = macromicro.MacroMicroScraper(headless=False, allow_manual_login=False)
    scraper.output_dir = tmp_path

    def _unexpected_session_gate():
        raise AssertionError("run should not preflight ensure_session before target fetch attempts")

    monkeypatch.setattr(scraper, "ensure_session", _unexpected_session_gate)
    monkeypatch.setattr(
        scraper,
        "_resolve_targets",
        lambda target_keys=None, urls=None: {
            "global-recession-rate": macromicro.DEFAULT_TARGETS["global-recession-rate"],
        },
    )
    monkeypatch.setattr(scraper, "_fetch_target_via_cookie_api", lambda target_key, spec: (_ for _ in ()).throw(RuntimeError("cookie api failed")))
    monkeypatch.setattr(
        scraper,
        "_capture_target",
        lambda target_key, spec: {"target_key": target_key, "success": True, "page_type": "chart"},
    )

    manifest = scraper.run(target_keys=["global-recession-rate"])

    assert manifest["success_count"] == 1


def test_run_raises_headed_retry_signal_when_headless_capture_hits_security_verification(monkeypatch, tmp_path):
    scraper = macromicro.MacroMicroScraper(headless=True, allow_manual_login=False)
    scraper.output_dir = tmp_path

    monkeypatch.setattr(
        scraper,
        "_resolve_targets",
        lambda target_keys=None, urls=None: {
            "global-recession-rate": macromicro.DEFAULT_TARGETS["global-recession-rate"],
        },
    )
    monkeypatch.setattr(scraper, "_supports_cookie_fetch", lambda target_key, spec: False)
    monkeypatch.setattr(
        scraper,
        "_capture_target",
        lambda target_key, spec: {
            "target_key": target_key,
            "success": False,
            "page_type": "chart",
            "error": "security_verification_incomplete",
            "title": "Just a moment...",
        },
    )

    try:
        scraper.run(target_keys=["global-recession-rate"])
    except RuntimeError as exc:
        assert "run non-headless" in str(exc)
    else:
        raise AssertionError("expected headless challenge to trigger headed retry signal")
