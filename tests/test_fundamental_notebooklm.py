import json
import pytest
from fundamental_research.notebooklm_research import (
    resolve_research_config,
    build_fundamental_questions,
    render_research_markdown,
    find_source_by_url,
)


def test_resolve_config_from_explicit_args():
    cfg = resolve_research_config(
        notebook_id="nb-abc123",
        storage_path="/tmp/auth.json",
        env={},
    )
    assert cfg["notebook_id"] == "nb-abc123"
    assert cfg["storage_path"] == "/tmp/auth.json"


def test_resolve_config_from_env():
    cfg = resolve_research_config(
        notebook_id=None,
        storage_path=None,
        env={"FUNDAMENTAL_NOTEBOOKLM_NOTEBOOK_ID_NVDA": "nb-nvda-xyz"},
        ticker="NVDA",
    )
    assert cfg["notebook_id"] == "nb-nvda-xyz"


def test_resolve_config_missing_notebook_id_raises():
    with pytest.raises(ValueError, match="notebook ID"):
        resolve_research_config(notebook_id=None, storage_path=None, env={}, ticker="AAPL")


def test_build_fundamental_questions_returns_four_keys():
    signal = {
        "ticker": "NVDA",
        "sector": "semiconductors",
        "trigger_source": "SMM_GOLDEN_EP",
        "trigger_signal": "sector_breakout",
        "youtube_urls": ["https://www.youtube.com/watch?v=abc123"],
    }
    questions = build_fundamental_questions(signal)
    assert set(questions.keys()) == {"earnings_change", "management_tone", "thesis_validity", "key_risks"}
    # Each question must mention the ticker
    for key, q in questions.items():
        assert "NVDA" in q, f"Question '{key}' does not mention ticker"


def test_build_fundamental_questions_sector_in_context():
    signal = {"ticker": "TSM", "sector": "foundry", "trigger_source": "DEEPVUE",
              "trigger_signal": "breakout", "youtube_urls": []}
    questions = build_fundamental_questions(signal)
    assert "foundry" in questions["thesis_validity"].lower() or "TSM" in questions["thesis_validity"]


def test_render_research_markdown_has_frontmatter():
    signal = {
        "ticker": "NVDA", "sector": "semiconductors",
        "trigger_source": "SMM_GOLDEN_EP", "trigger_signal": "sector_breakout",
        "youtube_urls": ["https://www.youtube.com/watch?v=abc123"],
    }
    answers = {
        "earnings_change": {"question": "Q1", "answer": "Revenue beat by 8%.", "conversation_id": "c1"},
        "management_tone": {"question": "Q2", "answer": "Bullish on data centre.", "conversation_id": "c1"},
        "thesis_validity": {"question": "Q3", "answer": "Intact.", "conversation_id": "c1"},
        "key_risks": {"question": "Q4", "answer": "Export restrictions.", "conversation_id": "c1"},
    }
    md = render_research_markdown(
        signal=signal,
        answers=answers,
        notebook_id="nb-nvda",
        notebook_title="FundamentalResearch_NVDA",
        synced_at="2026-03-24T10:00:00+00:00",
    )
    assert md.startswith("---"), "Must start with YAML frontmatter"
    assert "ticker: NVDA" in md
    assert "trigger_source: SMM_GOLDEN_EP" in md
    assert "## Earnings Change" in md
    assert "Revenue beat by 8%" in md
    assert "## Key Risks" in md


def test_render_research_markdown_youtube_urls_in_frontmatter():
    signal = {
        "ticker": "AAPL", "sector": "consumer_tech",
        "trigger_source": "MANUAL", "trigger_signal": "ad_hoc",
        "youtube_urls": ["https://www.youtube.com/watch?v=xyz"],
    }
    md = render_research_markdown(
        signal=signal, answers={}, notebook_id="nb-aapl",
        notebook_title="FundamentalResearch_AAPL",
        synced_at="2026-03-24T10:00:00+00:00",
    )
    assert "youtube_urls:" in md
    assert "watch?v=xyz" in md


def test_find_source_by_url_canonical_match():
    from fundamental_research.notebooklm_research import find_source_by_url

    class FakeSource:
        def __init__(self, url):
            self.url = url

    sources = [FakeSource("https://www.youtube.com/watch?v=abc123")]
    # youtu.be short URL should match canonical
    match = find_source_by_url(sources, "https://youtu.be/abc123")
    assert match is not None

    no_match = find_source_by_url(sources, "https://youtu.be/zzz999")
    assert no_match is None


# ── CLI helper tests ──────────────────────────────────────────

from scrape_fundamental_research import load_signal_from_file, build_signal_from_args


def test_load_signal_from_file(tmp_path):
    signal = {
        "ticker": "TSMC",
        "sector": "foundry",
        "trigger_source": "SMM_GOLDEN_EP",
        "trigger_signal": "sector_momentum",
        "youtube_urls": ["https://www.youtube.com/watch?v=test123"],
    }
    f = tmp_path / "signal.json"
    f.write_text(json.dumps(signal), encoding="utf-8")
    loaded = load_signal_from_file(str(f))
    assert loaded["ticker"] == "TSMC"
    assert len(loaded["youtube_urls"]) == 1


def test_build_signal_from_args():
    signal = build_signal_from_args(
        ticker="AMD",
        sector="semiconductors",
        trigger_source="DEEPVUE",
        trigger_signal="momentum_breakout",
        youtube_urls=["https://youtu.be/abc", "https://youtu.be/def"],
    )
    assert signal["ticker"] == "AMD"
    assert len(signal["youtube_urls"]) == 2
    assert "youtube.com/watch" in signal["youtube_urls"][0]  # canonicalized


def test_build_signal_from_args_normalises_ticker():
    signal = build_signal_from_args(
        ticker="nvda", sector="semis", trigger_source="MANUAL",
        trigger_signal="ad_hoc", youtube_urls=[],
    )
    assert signal["ticker"] == "NVDA"
