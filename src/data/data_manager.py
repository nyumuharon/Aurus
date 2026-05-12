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

