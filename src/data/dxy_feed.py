# src/data/dxy_feed.py
"""Aurus Sprint 1 — Stage 3: DXY (US Dollar Index) Feed
========================================================
Fetches DXY price and trend direction via MetaTrader 5.

Gold and DXY are inversely correlated — a rising DXY is bearish for gold,
a falling DXY is bullish. This module gives the system USD strength context.

Rules:
- All credentials come from config/settings.py — never hardcoded here.
- All errors are logged via the Python logging module — never use print().
- If DXY data is unavailable the module returns None without blocking other feeds.
"""

import logging
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)

# MetaTrader5 is Windows-only; on Linux/CI mt5 is None and tests inject a mock.
try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:
    mt5 = None  # type: ignore[assignment]

# DXY symbol as quoted on most MT5 brokers
_DXY_SYMBOL = "DXY"

# EMA neutrality band — if |EMA50 - EMA200| < this value, trend is NEUTRAL
_NEUTRAL_BAND = 0.05
