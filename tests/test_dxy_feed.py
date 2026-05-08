# tests/test_dxy_feed.py
"""Aurus Sprint 1 — Stage 3 Tests: DXY Feed
============================================
Unit tests for src/data/dxy_feed.py.

MetaTrader5 is mocked via module-level patching so all tests run on
Linux/CI without a live terminal.

Tests cover all 6 acceptance criteria from the Stage 3 build plan:
    1. get_dxy_price() returns a float greater than zero
    2. get_dxy_candles() returns a non-empty list
    3. calculate_ema() returns correct value for known input
    4. get_dxy_trend() returns dict with timestamp, price, trend keys
    5. trend value is one of BULLISH, BEARISH, or NEUTRAL
    6. Function handles empty candle list without crashing
"""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Build MT5 mock and inject before dxy_feed is imported
# ---------------------------------------------------------------------------

def _make_candle_array(n: int = 250, base_price: float = 104.0):
    """Return an n-row numpy recarray mimicking MT5 1H DXY candle data."""
    dtype = np.dtype([
        ("time", np.int64), ("open", np.float64), ("high", np.float64),
        ("low", np.float64), ("close", np.float64),
        ("tick_volume", np.int64), ("spread", np.int32), ("real_volume", np.int64),
    ])
    rows = [
        (1_740_826_800 + i * 3600, base_price, base_price + 0.5,
         base_price - 0.5, base_price + float(i) * 0.01, 100, 1, 0)
        for i in range(n)
    ]
    return np.array(rows, dtype=dtype)


def _make_mt5_mock() -> MagicMock:
    """Return a fully configured MetaTrader5 mock."""
    mock = MagicMock()
    mock.TIMEFRAME_H1 = 16385
    tick = MagicMock()
    tick.bid = 104.32
    mock.symbol_info_tick.return_value = tick
    mock.copy_rates_from_pos.return_value = _make_candle_array()
    mock.last_error.return_value = (0, "Success")
    return mock


MT5 = _make_mt5_mock()
sys.modules.setdefault("MetaTrader5", MT5)

import src.data.dxy_feed as dxy_feed  # noqa: E402

dxy_feed.mt5 = MT5  # force the module to use the mock regardless of platform


def _reset_mock():
    """Restore default passing state after a test mutates the mock."""
    tick = MagicMock()
    tick.bid = 104.32
    MT5.symbol_info_tick.return_value = tick
    MT5.copy_rates_from_pos.return_value = _make_candle_array()


# ---------------------------------------------------------------------------
# Test 1 — get_dxy_price() returns a float greater than zero
# ---------------------------------------------------------------------------

class TestGetDxyPrice:
    """Test 1: get_dxy_price() returns a float greater than zero."""

    def test_returns_float_greater_than_zero(self):
        """Test 1: get_dxy_price() must return a float > 0."""
        result = dxy_feed.get_dxy_price()
        assert isinstance(result, float), "get_dxy_price() must return a float"
        assert result > 0, "get_dxy_price() must return a value > 0"

    def test_returns_none_when_tick_unavailable(self):
        """get_dxy_price() returns None when MT5 returns no tick."""
        MT5.symbol_info_tick.return_value = None
        result = dxy_feed.get_dxy_price()
        assert result is None
        _reset_mock()


# ---------------------------------------------------------------------------
# Test 2 — get_dxy_candles() returns a non-empty list
# ---------------------------------------------------------------------------

class TestGetDxyCandles:
    """Test 2: get_dxy_candles() returns a non-empty list."""

    def test_returns_non_empty_list(self):
        """Test 2: get_dxy_candles() must return a non-empty list."""
        result = dxy_feed.get_dxy_candles()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_candle_has_required_keys(self):
        """Each candle dict contains time, open, high, low, close, volume."""
        result = dxy_feed.get_dxy_candles()
        required = {"time", "open", "high", "low", "close", "volume"}
        for candle in result:
            assert not (required - candle.keys())

    def test_returns_none_when_mt5_unavailable(self):
        """get_dxy_candles() returns None when MT5 copy_rates_from_pos fails."""
        MT5.copy_rates_from_pos.return_value = None
        result = dxy_feed.get_dxy_candles()
        assert result is None
        _reset_mock()

    def test_returns_empty_list_when_mt5_returns_empty(self):
        """get_dxy_candles() returns [] when MT5 returns an empty array."""
        MT5.copy_rates_from_pos.return_value = np.array([], dtype=np.float64)
        result = dxy_feed.get_dxy_candles()
        assert result == []
        _reset_mock()


# ---------------------------------------------------------------------------
# Test 3 — calculate_ema() returns correct value for known input
# ---------------------------------------------------------------------------

class TestCalculateEma:
    """Test 3: calculate_ema() returns correct value for a known input series."""

    def test_returns_correct_ema_for_known_input(self):
        """Test 3: EMA-3 of [1, 2, 3, 4, 5] should equal exactly 4.0."""
        # Manual derivation:
        #   k = 2/(3+1) = 0.5
        #   seed = (1+2+3)/3 = 2.0
        #   EMA after 4: 4 * 0.5 + 2.0 * 0.5 = 3.0
        #   EMA after 5: 5 * 0.5 + 3.0 * 0.5 = 4.0
        result = dxy_feed.calculate_ema([1.0, 2.0, 3.0, 4.0, 5.0], period=3)
        assert result == pytest.approx(4.0, rel=1e-6)

    def test_returns_none_for_insufficient_data(self):
        """calculate_ema() returns None when len(prices) < period."""
        result = dxy_feed.calculate_ema([1.0, 2.0], period=3)
        assert result is None

    def test_returns_none_for_empty_list(self):
        """calculate_ema() returns None when prices is an empty list."""
        result = dxy_feed.calculate_ema([], period=50)
        assert result is None

    def test_returns_float_for_large_series(self):
        """calculate_ema() returns a float for a 250-element series."""
        prices = [104.0 + i * 0.01 for i in range(250)]
        result = dxy_feed.calculate_ema(prices, period=200)
        assert isinstance(result, float)
        assert result > 0

