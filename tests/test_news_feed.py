# tests/test_news_feed.py
"""Aurus Sprint 1 — Stage 2 Tests: News Feed
=============================================
Unit tests for src/data/news_feed.py.

NewsAPI HTTP calls are mocked with unittest.mock so tests run offline
without a live API key.

Tests cover all 7 acceptance criteria from the Stage 2 build plan:
    1. get_latest_news() returns a non-empty list
    2. Each item contains timestamp, headline, source, sentiment keys
    3. classify_sentiment() returns "bullish" for a bullish headline
    4. classify_sentiment() returns "bearish" for a bearish headline
    5. classify_sentiment() returns "neutral" for a neutral headline
    6. get_gold_news() returns results without error
    7. Function returns None gracefully when API key is invalid
"""

from unittest.mock import MagicMock, patch

import pytest

import src.data.news_feed as news_feed


# ---------------------------------------------------------------------------
# Shared fixture — fake NewsAPI JSON response
# ---------------------------------------------------------------------------

def _fake_api_response(titles=None):
    """Build a mock requests.Response returning the given headline titles."""
    if titles is None:
        titles = [
            "Gold rally as Fed signals rate cut amid weak dollar",
            "Rate hike fears send gold drops lower as strong dollar dominates",
            "Markets await next central bank meeting data release",
        ]

    articles = [
        {
            "title": t,
            "publishedAt": "2026-03-01T10:00:00Z",
            "source": {"name": "Reuters"},
        }
        for t in titles
    ]

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"status": "ok", "articles": articles}
    return mock_resp


# ---------------------------------------------------------------------------
# Test 1 — get_latest_news() returns a non-empty list
# ---------------------------------------------------------------------------

class TestGetLatestNews:
    """Test 1 & 2: response is a non-empty list with correct keys."""

    @patch("src.data.news_feed.settings")
    @patch("src.data.news_feed.requests.get")
    def test_returns_non_empty_list(self, mock_get, mock_settings):
        """Test 1: get_latest_news() returns a non-empty list."""
        mock_settings.NEWS_API_KEY = "test-key-123"
        mock_get.return_value = _fake_api_response()

        result = news_feed.get_latest_news("gold", count=3)

        assert isinstance(result, list)
        assert len(result) > 0

    @patch("src.data.news_feed.settings")
    @patch("src.data.news_feed.requests.get")
    def test_each_item_has_required_keys(self, mock_get, mock_settings):
        """Test 2: Each item contains timestamp, headline, source, sentiment."""
        mock_settings.NEWS_API_KEY = "test-key-123"
        mock_get.return_value = _fake_api_response()

        result = news_feed.get_latest_news("gold", count=3)
        required = {"timestamp", "headline", "source", "sentiment"}

        for item in result:
            missing = required - item.keys()
            assert not missing, f"Item missing keys: {missing}"

    @patch("src.data.news_feed.settings")
    @patch("src.data.news_feed.requests.get")
    def test_returns_empty_list_when_api_returns_no_articles(self, mock_get, mock_settings):
        """get_latest_news() returns [] when API articles list is empty."""
        mock_settings.NEWS_API_KEY = "test-key-123"
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_resp

        result = news_feed.get_latest_news("gold")
        assert result == []


# ---------------------------------------------------------------------------
# Tests 3–5 — classify_sentiment()
# ---------------------------------------------------------------------------

class TestClassifySentiment:
    """Tests 3–5: sentiment classification for bullish, bearish, neutral."""

    def test_bullish_headline(self):
        """Test 3: classify_sentiment returns 'bullish' for a bullish headline."""
        bullish_cases = [
            "Fed signals rate cut amid economic slowdown",
            "Dovish Fed commentary sends gold rally higher",
            "Inflation falls to two-year low boosting gold",
            "Gold rally continues as weak dollar pressures markets",
            "War fears drive safe-haven demand",
            "Financial crisis triggers gold surge",
        ]
        for headline in bullish_cases:
            result = news_feed.classify_sentiment(headline)
            assert result == "bullish", f"Expected 'bullish' for: '{headline}', got '{result}'"

    def test_bearish_headline(self):
        """Test 4: classify_sentiment returns 'bearish' for a bearish headline."""
        bearish_cases = [
            "Fed eyes another rate hike to combat inflation",
            "Hawkish Fed minutes push dollar higher",
            "Strong dollar weighs on gold prices",
            "Gold drops as risk appetite returns to markets",
            "Risk on sentiment drives equities higher",
        ]
        for headline in bearish_cases:
            result = news_feed.classify_sentiment(headline)
            assert result == "bearish", f"Expected 'bearish' for: '{headline}', got '{result}'"

    def test_neutral_headline(self):
        """Test 5: classify_sentiment returns 'neutral' for a neutral headline."""
        neutral_cases = [
            "Central bank meets next Tuesday for policy review",
            "Markets await jobs data release on Friday",
            "Gold trades sideways ahead of US CPI print",
            "Investors monitor oil prices and equities",
        ]
        for headline in neutral_cases:
            result = news_feed.classify_sentiment(headline)
            assert result == "neutral", f"Expected 'neutral' for: '{headline}', got '{result}'"


# ---------------------------------------------------------------------------
# Test 6 — get_gold_news() returns results without error
# ---------------------------------------------------------------------------

class TestGetGoldNews:
    """Test 6: get_gold_news() returns results without error."""

    @patch("src.data.news_feed.settings")
    @patch("src.data.news_feed.requests.get")
    def test_get_gold_news_returns_results(self, mock_get, mock_settings):
        """Test 6: get_gold_news() returns a list without raising."""
        mock_settings.NEWS_API_KEY = "test-key-123"
        mock_get.return_value = _fake_api_response()

        try:
            result = news_feed.get_gold_news()
        except Exception as exc:
            pytest.fail(f"get_gold_news() raised an exception: {exc}")

        assert isinstance(result, list)
        assert len(result) > 0

    @patch("src.data.news_feed.settings")
    @patch("src.data.news_feed.requests.get")
    def test_get_usd_news_returns_results(self, mock_get, mock_settings):
        """get_usd_news() returns a list without raising."""
        mock_settings.NEWS_API_KEY = "test-key-123"
        mock_get.return_value = _fake_api_response()

        result = news_feed.get_usd_news()
        assert isinstance(result, list)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 7 — returns None gracefully when API key is invalid / missing
# ---------------------------------------------------------------------------

class TestInvalidApiKey:
    """Test 7: returns None gracefully when API key is missing or invalid."""

    @patch("src.data.news_feed.settings")
    def test_returns_none_when_api_key_empty(self, mock_settings):
        """Test 7a: get_latest_news() returns None when NEWS_API_KEY is empty."""
        mock_settings.NEWS_API_KEY = ""
        result = news_feed.get_latest_news("gold")
        assert result is None

    @patch("src.data.news_feed.settings")
    def test_returns_none_when_api_key_none(self, mock_settings):
        """Test 7b: get_latest_news() returns None when NEWS_API_KEY is None."""
        mock_settings.NEWS_API_KEY = None
        result = news_feed.get_latest_news("gold")
        assert result is None

    @patch("src.data.news_feed.settings")
    @patch("src.data.news_feed.requests.get")
    def test_returns_none_after_both_retries_fail(self, mock_get, mock_settings):
        """Test 7c: returns None when API raises on both attempts."""
        mock_settings.NEWS_API_KEY = "bad-key"
        mock_get.side_effect = Exception("Connection error")

        with patch("src.data.news_feed.time.sleep"):  # skip real sleep
            result = news_feed.get_latest_news("gold")

        assert result is None
