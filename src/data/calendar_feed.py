# src/data/calendar_feed.py
"""Aurus Sprint 1 — Stage 4: Economic Calendar Feed
====================================================
Fetches today's high-impact economic events from the Forex Factory public
calendar JSON feed. Used to avoid opening new trades during high-impact
news releases — a critical prop firm survival rule.

Rules:
- All errors are logged via the Python logging module — never use print().
- Calendar failure must never block other feeds — treat as no upcoming events.
- is_high_impact_window() always returns False (safe) when data is unavailable.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from config import settings

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Calendar API — Forex Factory public JSON feed (no key required)
# ---------------------------------------------------------------------------
_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_REQUEST_TIMEOUT = 10       # seconds
_RETRY_DELAY = 5            # seconds — single retry on failure

# ---------------------------------------------------------------------------
# Filtering constants (per build plan)
# ---------------------------------------------------------------------------
_VALID_CURRENCIES = {"USD", "XAU"}
_VALID_IMPACTS = {"High", "Medium"}        # Forex Factory uses Title-case
_HIGH_IMPACT_WINDOW_MINUTES = 15           # ±15 min around a HIGH event
