from __future__ import annotations

from liquidity.h_model_parser import classify_h_model_direction, parse_h_model_article


def test_classify_h_model_direction_detects_expanding_language():
    result = classify_h_model_direction(
        "US liquidity is improving. Added liquidity is supporting markets and easing repo stress."
    )

    assert result["liquidity_direction"] == "EXPANDING"
    assert result["market_bias"] == "RISK_ON"
    assert result["signal_score"] > 0


def test_classify_h_model_direction_detects_contracting_language():
    result = classify_h_model_direction(
        "Liquidity is peaking. Rotation is moving into defensive sectors and cash. Risk off is rising."
    )

    assert result["liquidity_direction"] == "CONTRACTING"
    assert result["market_bias"] == "RISK_OFF"
    assert result["signal_score"] < 0


def test_parse_h_model_article_marks_carry_forward_when_using_previous():
    payload = {
        "captured_at": "2026-03-09T12:00:00+00:00",
        "articles": [
            {
                "url": "https://capitalwars.substack.com/p/unrelated",
                "title": "Unrelated Article",
                "date": "2026-03-09T08:00:00+00:00",
                "body_text": "This article is about politics and nothing else.",
            }
        ],
        "previous": {
            "provider": "capital_wars_michael_howell",
            "article_url": "https://capitalwars.substack.com/p/old",
            "title": "Older Liquidity View",
            "published_at": "2026-03-05T00:00:00+00:00",
            "captured_at": "2026-03-05T02:00:00+00:00",
            "freshness": "aging",
            "staleness_hours": 90.0,
            "liquidity_direction": "FLAT",
            "market_bias": "TRANSITION",
            "signal_score": -5,
            "relevance_score": 8,
            "carry_forward": False,
            "evidence": ["Liquidity is peaking."],
            "screenshot_path": "",
            "available": True,
        },
    }

    parsed = parse_h_model_article(payload, now_iso="2026-03-09T12:00:00+00:00")

    assert parsed["carry_forward"] is True
    assert parsed["article_url"] == "https://capitalwars.substack.com/p/old"


def test_parse_h_model_article_sets_freshness_boundaries():
    payload = {
        "captured_at": "2026-03-09T12:00:00+00:00",
        "articles": [
            {
                "url": "https://capitalwars.substack.com/p/fresh",
                "title": "Fresh Liquidity",
                "date": "2026-03-06T12:00:00+00:00",
                "body_text": "US liquidity is improving and markets have support.",
            }
        ],
    }

    parsed = parse_h_model_article(payload, now_iso="2026-03-09T12:00:00+00:00")

    assert parsed["freshness"] == "fresh"
    assert 71.9 <= parsed["staleness_hours"] <= 72.1
    assert parsed["evidence"]
