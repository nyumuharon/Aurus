# src/data/news_feed.py
"""Aurus Sprint 1 — Stage 2: News Feed
======================================
Fetches the latest financial news headlines related to Gold (XAU), USD, and
Federal Reserve policy from NewsAPI. Provides market sentiment context to the
AI validator in Layer 3.

Rules:
- All credentials come from config/settings.py — never hardcoded here.
- All errors are logged via the Python logging module — never use print().
- API failures retry once after 5 seconds; return None if retry fails.
- A news failure must never crash the system — news is supplementary data.
"""

import logging
import time
from datetime import datetime

import requests

from config import settings

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NewsAPI endpoint
# ---------------------------------------------------------------------------
_NEWSAPI_URL = "https://newsapi.org/v2/everything"
_RETRY_DELAY = 5  # seconds — retry once after this delay

# ---------------------------------------------------------------------------
# Sentiment keyword tables (case-insensitive substring matching)
# ---------------------------------------------------------------------------
_BULLISH_KEYWORDS = [
    "rate cut",
    "dovish",
    "inflation falls",
    "gold rally",
    "weak dollar",
    "war",
    "crisis",
]

_BEARISH_KEYWORDS = [
    "rate hike",
    "hawkish",
    "strong dollar",
    "gold drops",
    "risk on",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_sentiment(headline: str) -> str:
    """Classify a single news headline as bullish, bearish, or neutral.

    Uses keyword matching against the Aurus sentiment keyword tables.
    Bullish keywords are checked first; bearish second. If neither matches
    the result is neutral.

    Args:
        headline: Raw headline string from NewsAPI.

    Returns:
        ``"bullish"``, ``"bearish"``, or ``"neutral"``.
    """
    lower = headline.lower()

    for kw in _BULLISH_KEYWORDS:
        if kw in lower:
            return "bullish"

    for kw in _BEARISH_KEYWORDS:
        if kw in lower:
            return "bearish"

    return "neutral"


def get_latest_news(query: str, count: int = 10):
    """Fetch the latest *count* headlines matching *query* from NewsAPI.

    Retries once after a 5-second delay on request failure.

    Args:
        query: Search string forwarded to NewsAPI (e.g. ``"gold XAU"``).
        count: Maximum number of articles to return (default: 10).

    Returns:
        list[dict] — articles in standard format with sentiment classified.
        []         — API returned zero results.
        None       — API key missing, or all retries failed.
    """
    api_key = settings.NEWS_API_KEY
    if not api_key:
        logger.error("NEWS_API_KEY is not set in config/settings.py.")
        return None

    params = {
        "q": query,
        "pageSize": count,
        "language": "en",
        "sortBy": "publishedAt",
        "apiKey": api_key,
    }

    for attempt in range(1, 3):  # max 2 attempts (original + 1 retry)
        try:
            response = requests.get(_NEWSAPI_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            articles = data.get("articles", [])
            if not articles:
                logger.warning("NewsAPI returned zero articles for query '%s'.", query)
                return []

            result = []
            for article in articles:
                published = article.get("publishedAt", "")
                try:
                    ts = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
                    timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                headline = article.get("title", "") or ""
                source = (article.get("source") or {}).get("name", "Unknown")
                sentiment = classify_sentiment(headline)

                result.append(
                    {
                        "timestamp": timestamp,
                        "headline": headline,
                        "source": source,
                        "sentiment": sentiment,
                    }
                )

            logger.info(
                "NewsAPI returned %d articles for query '%s'.", len(result), query
            )
            return result

        except Exception as exc:
            logger.error(
                "NewsAPI request failed (attempt %d/2) for query '%s': %s",
                attempt, query, exc,
            )
            if attempt == 1:
                logger.info("Retrying NewsAPI in %d seconds…", _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)

    logger.error("All retries failed for NewsAPI query '%s'.", query)
    return None


def get_gold_news(count: int = 10):
    """Fetch the latest gold-related headlines from NewsAPI.

    Convenience wrapper around :func:`get_latest_news` using a gold-specific
    search query.

    Args:
        count: Maximum number of articles to return (default: 10).

    Returns:
        list[dict] — articles in standard format, or [] or None (see
        :func:`get_latest_news` for details).
    """
    return get_latest_news(query="gold XAU XAUUSD", count=count)


def get_usd_news(count: int = 10):
    """Fetch the latest USD and Federal Reserve headlines from NewsAPI.

    Convenience wrapper around :func:`get_latest_news` using a USD-specific
    search query.

    Args:
        count: Maximum number of articles to return (default: 10).

    Returns:
        list[dict] — articles in standard format, or [] or None (see
        :func:`get_latest_news` for details).
    """
    return get_latest_news(query="USD dollar Federal Reserve Fed", count=count)
