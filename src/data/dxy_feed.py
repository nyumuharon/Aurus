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


def calculate_ema(prices: list, period: int):
    """Calculate the Exponential Moving Average (EMA) for a list of prices.

    Uses the standard EMA formula with a smoothing factor of 2/(period+1).
    The first EMA value is seeded with the simple average of the first
    *period* prices.

    Args:
        prices: Ordered list of float prices (oldest first).
        period: EMA lookback period (e.g. 50, 200).

    Returns:
        float — the final EMA value for the given price series.
        None  — if prices is empty or has fewer elements than period.
    """
    if not prices or len(prices) < period:
        logger.warning(
            "Insufficient data to calculate EMA-%d (got %d prices).",
            period, len(prices) if prices else 0,
        )
        return None

    k = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period  # seed with SMA of first `period` values
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    return ema


def get_dxy_price():
    """Fetch the current DXY spot price from MetaTrader 5.

    Returns:
        float — current DXY bid price.
        None  — if MT5 is unavailable or the symbol tick cannot be retrieved.
    """
    if mt5 is None:
        logger.warning("MetaTrader5 not available — cannot fetch DXY price.")
        return None

    tick = mt5.symbol_info_tick(_DXY_SYMBOL)
    if tick is None:
        logger.warning(
            "MT5 returned no tick data for symbol '%s': %s",
            _DXY_SYMBOL, mt5.last_error(),
        )
        return None

    price = float(tick.bid)
    logger.info("DXY spot price: %.4f", price)
    return price
