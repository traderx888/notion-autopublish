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


def test_load_latest_h_model_article_reads_raw_file(tmp_path: Path):
    raw_path = tmp_path / "h_model_latest_raw.json"
    raw_path.write_text(
        json.dumps({"available": True, "articles": [{"title": "Saved"}]}),
        encoding="utf-8",
    )

    payload = load_latest_h_model_article(tmp_path)

    assert payload["articles"][0]["title"] == "Saved"
