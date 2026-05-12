# src/data/data_manager.py
"""Aurus Sprint 1 — Stage 5: Data Manager
========================================
The single entry point for all data in Aurus. Orchestrates all four feed
modules, runs them on their correct schedules, and delivers one clean
unified data snapshot to Layer 2 (Pattern Detection).

Rules:
- All errors are logged via the Python logging module — never use print().
- Data Manager must never crash regardless of individual feed failures.
- If price feed fails, status is ERROR.
- If news/calendar/DXY feeds fail, status is DEGRADED.
"""

import logging
import time
import threading
from datetime import datetime

import schedule

from src.data import calendar_feed, dxy_feed, news_feed, price_feed

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------
_is_running = False
_scheduler_thread = None

_latest_news = []
_latest_dxy = {"timestamp": "", "price": 0.0, "trend": "NEUTRAL"}
_todays_events = []

# ---------------------------------------------------------------------------
# Background update tasks
# ---------------------------------------------------------------------------

def _update_news():
    """Fetch latest news and update internal state."""
    global _latest_news
    try:
        news = news_feed.get_gold_news()
        if news is not None:
            _latest_news = news
    except Exception as exc:
        logger.error("Data Manager: error updating news: %s", exc)


def _update_dxy():
    """Fetch latest DXY trend and update internal state."""
    global _latest_dxy
    try:
        trend = dxy_feed.get_dxy_trend()
        if trend is not None:
            _latest_dxy = trend
    except Exception as exc:
        logger.error("Data Manager: error updating DXY: %s", exc)


def _update_calendar():
    """Fetch today's events and update internal state."""
    global _todays_events
    try:
        events = calendar_feed.get_todays_events()
        # Even if events is [], we update, since that might mean no more events today.
        # But if the API failed entirely (e.g. exception), we might want to keep old data or handle it.
        # calendar_feed returns [] on failure, so we'll just update.
        _todays_events = events
    except Exception as exc:
        logger.error("Data Manager: error updating calendar: %s", exc)

def _scheduler_loop():
    """Run scheduled tasks in a background thread."""
    while _is_running:
        schedule.run_pending()
        time.sleep(1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start() -> bool:
    """Initialize all feed connections and start background polling.

    Returns:
        True  — initialization successful.
        False — failed to start (e.g. price feed connect failed).
    """
    global _is_running, _scheduler_thread

    if _is_running:
        logger.warning("Data Manager: start() called but already running.")
        return True

    logger.info("Data Manager: initializing feeds...")

    if not price_feed.connect():
        logger.error("Data Manager: failed to connect to price feed.")
        return False

    # Do initial synchronous fetches for background feeds
    _update_news()
    _update_dxy()
    _update_calendar()

    # Schedule background updates
    schedule.clear()
    schedule.every(5).minutes.do(_update_news)
    schedule.every(1).minutes.do(_update_dxy)
    schedule.every(1).hours.do(_update_calendar)

    _is_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()

    logger.info("Data Manager: started successfully.")
    return True


def stop() -> None:
    """Cleanly shut down all connections and the background scheduler."""
    global _is_running, _scheduler_thread

    if not _is_running:
        return

    logger.info("Data Manager: stopping...")
    _is_running = False
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=2.0)

    price_feed.disconnect()
    logger.info("Data Manager: stopped successfully.")
