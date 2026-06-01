from __future__ import annotations

import json
from pathlib import Path

from liquidity.h_model_source import capture_latest_h_model, load_latest_h_model_article


class FakePage:
    def __init__(self):
        self.screenshots = []

    def screenshot(self, path: str):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        self.screenshots.append(target)


class FakeReader:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.page = FakePage()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read_author_page(self, url: str, limit: int = 3):
        return [
            {
                "url": "https://capitalwars.substack.com/p/post-1",
                "title": "Liquidity Rising Again",
                "date": "2026-03-09T00:00:00+00:00",
                "body_text": "US liquidity is improving and repo stress is easing.",
            }
        ]


def test_capture_latest_h_model_writes_raw_and_screenshot(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("H_MODEL_SOURCE", "substack")
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(tmp_path))
    monkeypatch.setattr("liquidity.h_model_source.SubstackAuthorReader", FakeReader)

    payload = capture_latest_h_model("https://substack.com/@capitalwars", limit=3, headless=True)

    raw_path = tmp_path / "h_model_latest_raw.json"
    screenshot_path = tmp_path / "h_model_latest_screenshot.png"
    assert payload["available"] is True
    assert payload["articles"][0]["title"] == "Liquidity Rising Again"
    assert raw_path.exists()
    assert screenshot_path.exists()
    saved = json.loads(raw_path.read_text(encoding="utf-8"))
    assert saved["articles"][0]["url"] == "https://capitalwars.substack.com/p/post-1"


def test_capture_latest_h_model_degrades_on_error(tmp_path: Path, monkeypatch):
    class BrokenReader(FakeReader):
        def read_author_page(self, url: str, limit: int = 3):
            raise RuntimeError("boom")

    monkeypatch.setenv("H_MODEL_SOURCE", "substack")
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(tmp_path))
    monkeypatch.setattr("liquidity.h_model_source.SubstackAuthorReader", BrokenReader)
    fallback_path = tmp_path / "fallback.json"
    fallback_path.write_text(
        json.dumps(
            {
                "url": "https://capitalwars.substack.com/p/fallback",
                "title": "Fallback Liquidity",
                "date": "2026-03-08T00:00:00+00:00",
                "body_text": "Global liquidity is peaking and rotation is turning defensive.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("liquidity.h_model_source.FALLBACK_ARTICLE_PATH", fallback_path)

    payload = capture_latest_h_model("https://substack.com/@capitalwars", limit=3, headless=True)

    assert payload["available"] is True
    assert payload["capture_status"] == "fallback_existing"
    assert payload["articles"][0]["title"] == "Fallback Liquidity"


def test_capture_latest_h_model_can_use_notion_source(tmp_path: Path, monkeypatch):
    def fake_capture_latest_notion_capital_wars(**kwargs):
        return {
            "articles": [
                {
                    "url": "https://www.notion.so/gli-apr15",
                    "title": "Global Liquidity Watch: Weekly Update Apr 15, 2026",
                    "date": "2026-04-15T00:00:00+00:00",
                    "body_text": "Global Liquidity to US$188.1tr and 3m annualized growth rate is 4.0%.",
                }
            ],
            "available": True,
            "capture_status": "notion_ok",
            "text_artifact_path": str(tmp_path / "notion" / "michael_howell_capital_war_latest.txt"),
        }

    class FailingReader(FakeReader):
        def read_author_page(self, url: str, limit: int = 3):
            raise AssertionError("Substack should not be called when Notion succeeds")

    monkeypatch.setenv("H_MODEL_SOURCE", "notion")
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("NOTION_TOKEN", "secret")
    monkeypatch.setenv("H_MODEL_NOTION_PARENT_PAGE_ID", "15d3caa8a48780bf84ffcc796104a627")
    monkeypatch.setattr(
        "liquidity.h_model_source.capture_latest_notion_capital_wars",
        fake_capture_latest_notion_capital_wars,
    )
    monkeypatch.setattr("liquidity.h_model_source.SubstackAuthorReader", FailingReader)

    payload = capture_latest_h_model("https://substack.com/@capitalwars", limit=3, headless=True)

    assert payload["available"] is True
    assert payload["capture_status"] == "notion_ok"
    assert payload["articles"][0]["url"] == "https://www.notion.so/gli-apr15"


def test_capture_latest_h_model_reads_fundman_env_token_when_local_missing(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    notion_repo = workspace / "notion-autopublish"
    fundman_repo = workspace / "fundman-jarvis"
    notion_repo.mkdir(parents=True)
    fundman_repo.mkdir(parents=True)
    (fundman_repo / ".env").write_text("NOTION_TOKEN=from_fundman\n", encoding="utf-8")
    seen = {}

    def fake_capture_latest_notion_capital_wars(**kwargs):
        seen["token"] = kwargs["token"]
        return {
            "articles": [
                {
                    "url": "https://www.notion.so/gli-apr21",
                    "title": "Global Liquidity Watch: Weekly Update Apr 21, 2026",
                    "date": "2026-04-21T00:00:00+00:00",
                    "body_text": "Global Liquidity rose to US$189.1tr.",
                }
            ],
            "available": True,
            "capture_status": "notion_ok",
        }

    class FailingReader(FakeReader):
        def read_author_page(self, url: str, limit: int = 3):
            raise AssertionError("Substack should not be called when sibling .env has token")

    monkeypatch.setattr("liquidity.h_model_source.PROJECT_ROOT", notion_repo)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("H_MODEL_NOTION_TOKEN", raising=False)
    monkeypatch.setenv("H_MODEL_SOURCE", "notion")
    monkeypatch.setenv("LIQUIDITY_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(
        "liquidity.h_model_source.capture_latest_notion_capital_wars",
        fake_capture_latest_notion_capital_wars,
    )
    monkeypatch.setattr("liquidity.h_model_source.SubstackAuthorReader", FailingReader)

    payload = capture_latest_h_model("https://substack.com/@capitalwars", limit=3, headless=True)

    assert seen["token"] == "from_fundman"
    assert payload["capture_status"] == "notion_ok"
    assert payload["articles"][0]["title"] == "Global Liquidity Watch: Weekly Update Apr 21, 2026"


def test_load_latest_h_model_article_reads_raw_file(tmp_path: Path):
    raw_path = tmp_path / "h_model_latest_raw.json"
    raw_path.write_text(
        json.dumps({"available": True, "articles": [{"title": "Saved"}]}),
        encoding="utf-8",
    )

    payload = load_latest_h_model_article(tmp_path)

    assert payload["articles"][0]["title"] == "Saved"
