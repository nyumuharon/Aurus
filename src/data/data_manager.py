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


def is_ready() -> bool:
    """Check if the system is fully initialized and price feed is alive.

    Returns:
        True  — system is running and MT5 is connected.
        False — system not started, or price feed disconnected.
    """
    if not _is_running:
        return False
    return price_feed.is_connected()


def get_market_snapshot() -> dict:
    """Return a unified dictionary of all market data for the current tick.

    Assembles data from the price, news, DXY, and calendar feeds into a
    single dictionary. Calculates overall system status.

    Returns:
        dict — unified data snapshot matching the Sprint 1 requirements.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Price feed (synchronous, on-demand)
    candles_1m = price_feed.get_latest_candles(timeframe=price_feed.mt5.TIMEFRAME_M1 if price_feed.mt5 else None, count=60)
    candles_15m = price_feed.get_latest_candles(timeframe=price_feed.mt5.TIMEFRAME_M15 if price_feed.mt5 else None, count=200)

    price_status = "OK"
    if candles_1m is None or candles_15m is None:
        price_status = "ERROR"
        logger.error("Data Manager: Price feed failed during snapshot.")

    latest_candle = {}
    if candles_1m:
        latest_candle = candles_1m[-1]

    # 2. Background feeds (from memory)
    news_status = "OK" if _latest_news else "ERROR"
    dxy_status = "OK" if _latest_dxy and _latest_dxy.get("price") else "ERROR"
    # Calendar doesn't strictly have an error vs empty distinction in memory
    # but we can assume if it's empty it might be fine, but let's just evaluate overall status
    
    # 3. Overall status
    if price_status == "ERROR":
        status = "ERROR"
    elif not _latest_news or not _latest_dxy.get("price"):
        status = "DEGRADED"
    else:
        status = "OK"

    # 4. Assemble
    return {
        "timestamp": timestamp,
        "price": {
            "latest_candle": latest_candle,
            "candles_1m": candles_1m or [],
            "candles_15m": candles_15m or [],
        },
        "news": _latest_news,
        "dxy": _latest_dxy,
        "calendar": {
            "events_today": _todays_events,
            "high_impact_window": calendar_feed.is_high_impact_window(_todays_events),
        },
        "status": status,
    }
