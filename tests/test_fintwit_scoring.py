"""Tests for FinTwit signal scoring — false positive prevention."""
import pytest
from datetime import datetime, timezone, timedelta
from monitor_fintwit import score_content, score_tweet, load_config


@pytest.fixture
def config():
    return load_config()


def _make_tweet(text, handle="TestUser", likes=50, retweets=10, replies=5, minutes_ago=30):
    created = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "id": "test_001",
        "handle": handle,
        "text": text,
        "created_at": created,
        "created_at_str": created.isoformat(),
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "views": 10000,
        "url": "",
        "is_retweet": False,
    }


# ── Direction false positives ──────────────────────────────────────────

class TestDirectionFalsePositives:

    def test_long_discussion_no_match(self, config):
        text = ("Today I had the pleasure to have a three hour long discussion "
                "with @DavidLe76335983 at the JW Marriott Hong Kong. "
                "Thanks David, it is nice to see you again. #Gold #Silver")
        assert score_content(text, config) == 0

    def test_long_time_no_match(self, config):
        assert score_content("It's been a long time since I posted", config) <= 0

    def test_short_film_no_match(self, config):
        assert score_content("Just watched a short film about Wall Street", config) <= 0

    def test_long_story_short_no_match(self, config):
        assert score_content("Long story short, markets are unpredictable", config) <= 0


# ── Direction true positives ───────────────────────────────────────────

class TestDirectionTruePositives:

    def test_im_long_gold(self, config):
        assert score_content("I'm long gold here. Generational buying opportunity.", config) >= 20

    def test_going_long_cashtag(self, config):
        assert score_content("Going long $NVDA ahead of earnings", config) >= 20

    def test_long_position(self, config):
        assert score_content("Long position in $FNMA. Absurdly cheap.", config) >= 45

    def test_going_short_cashtag(self, config):
        assert score_content("Going short $TSLA ahead of earnings", config) >= 20

    def test_shorting_always_financial(self, config):
        assert score_content("Shorting $GME here, overvalued", config) >= 20

    def test_bullish_unambiguous(self, config):
        assert score_content("Extremely bullish on gold at these levels", config) >= 20

    def test_buy_sell_unambiguous(self, config):
        assert score_content("Buy $GLD here", config) >= 20


# ── Social noise penalty ──────────────────────────────────────────────

class TestSocialNoisePenalty:

    def test_meeting_at_hotel_penalized(self, config):
        text = ("Today I had the pleasure to have a discussion "
                "at the JW Marriott Hong Kong. #Gold #Silver")
        assert score_content(text, config) <= 0

    def test_speaking_at_event(self, config):
        assert score_content("Speaking at the Bloomberg commodities forum today", config) <= 0

    def test_dinner_social(self, config):
        text = "Great dinner with @someone at the Ritz. Always good catching up."
        assert score_content(text, config) <= 0


# ── Content gate (min_content_score) ──────────────────────────────────

class TestContentGate:

    def test_no_content_capped_below_threshold(self, config):
        """High-tier account + high engagement but zero content should not alert."""
        tweet = _make_tweet(
            "Beautiful day in Hong Kong. #Gold #Silver",
            handle="KingKong9888",
            likes=500, retweets=200, replies=100, minutes_ago=10,
        )
        result = score_tweet(tweet, config)
        assert result["scores"]["final"] < 60

    def test_with_content_not_capped(self, config):
        """Genuine signal should pass threshold normally."""
        tweet = _make_tweet(
            "I'm long $FNMA. Absurdly undervalued at these levels.",
            handle="michaeljburry",
            likes=1000, retweets=500, replies=200, minutes_ago=10,
        )
        result = score_tweet(tweet, config)
        assert result["scores"]["final"] >= 60


# ── Known true positives (regression) ────────────────────────────────

class TestKnownTruePositives:

    def test_burry_fnma_letter(self, config):
        text = ("Open Letter on Housing, Fannie & Freddie "
                "@realDonaldTrump @pulte $fnma $FMCC "
                "We strongly urge release. Absurdly undervalued.")
        assert score_content(text, config) >= 40

    def test_kingkong_gold_4200(self, config):
        text = ("#Gold at $4,200 — is that the top? Jamie Dimon says "
                "rally could go further. We added to our position.")
        assert score_content(text, config) >= 25
