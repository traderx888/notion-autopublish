from __future__ import annotations

import json
from pathlib import Path

from liquidity.notion_capital_wars_source import (
    capture_latest_notion_capital_wars,
    extract_notion_page_id,
)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []
        self.parent_id = "15d3caa8a48780bf84ffcc796104a627"
        self.gli_id = "3443caa8a487800894f9c697cb03137a"

    def get(self, url: str, headers=None, params=None, timeout=30):
        self.calls.append((url, params))
        if url.endswith(f"/blocks/{self.parent_id}/children"):
            return FakeResponse(
                {
                    "results": [
                        {
                            "id": "34b3caa8a48780c3b9fad5257e0d399f",
                            "type": "child_page",
                            "child_page": {
                                "title": "Markets Are Misreading A Late Cycle Liquidity Crunch | Michael Howell 22/4/2026"
                            },
                            "last_edited_time": "2026-04-23T09:10:00.000Z",
                        },
                        {
                            "id": "3483caa8a48780ee940bf882c4feba3d",
                            "type": "child_page",
                            "child_page": {"title": "The Ticking Clock Apr 19, 2026"},
                            "last_edited_time": "2026-04-20T10:50:36.432Z",
                        },
                        {
                            "id": self.gli_id,
                            "type": "child_page",
                            "child_page": {
                                "title": "Global Liquidity Watch: Weekly Update Apr 15, 2026"
                            },
                            "last_edited_time": "2026-04-16T13:43:58.389Z",
                        },
                        {
                            "id": "3353caa8a48780bd913cf15c31d39c53",
                            "type": "child_page",
                            "child_page": {
                                "title": "Global Liquidity Watch: Weekly Update Mar 31, 2026"
                            },
                            "last_edited_time": "2026-04-01T07:30:00.000Z",
                        },
                    ],
                    "has_more": False,
                }
            )
        if url.endswith(f"/blocks/{self.gli_id}/children"):
            return FakeResponse(
                {
                    "results": [
                        {
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {
                                        "plain_text": (
                                            "Latest flash estimates record a slight pickup "
                                            "in Global Liquidity to US$188.1tr."
                                        )
                                    }
                                ]
                            },
                        },
                        {
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [
                                    {"plain_text": "The 3m annualized growth rate is 4.0%."}
                                ]
                            },
                        },
                    ],
                    "has_more": False,
                }
            )
        raise AssertionError(f"unexpected URL {url}")


def test_extract_notion_page_id_accepts_url_and_plain_id():
    assert (
        extract_notion_page_id(
            "https://www.notion.so/Michael-Howell-Capital-War-15d3caa8a48780bf84ffcc796104a627"
        )
        == "15d3caa8a48780bf84ffcc796104a627"
    )
    assert extract_notion_page_id("3443caa8-a487-8008-94f9-c697cb03137a") == (
        "3443caa8a487800894f9c697cb03137a"
    )


def test_capture_latest_notion_capital_wars_exports_latest_gli_page(tmp_path: Path):
    payload = capture_latest_notion_capital_wars(
        token="secret",
        parent_page_id="15d3caa8a48780bf84ffcc796104a627",
        output_dir=tmp_path,
        session=FakeSession(),
        now_iso="2026-04-23T01:02:03+00:00",
    )

    assert payload["available"] is True
    assert payload["capture_status"] == "notion_ok"
    assert payload["articles"][0]["title"] == "Global Liquidity Watch: Weekly Update Apr 15, 2026"
    assert payload["articles"][0]["date"] == "2026-04-15T00:00:00+00:00"
    assert "US$188.1tr" in payload["articles"][0]["body_text"]

    text_path = tmp_path / "michael_howell_capital_war_latest.txt"
    json_path = tmp_path / "michael_howell_capital_war_latest.json"
    text = text_path.read_text(encoding="utf-8")
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))

    assert "TITLE: Global Liquidity Watch: Weekly Update Apr 15, 2026" in text
    assert "PUBLISHED_AT: 2026-04-15T00:00:00+00:00" in text
    assert "Global Liquidity to US$188.1tr" in text
    assert sidecar["article_page_id"] == "3443caa8a487800894f9c697cb03137a"
