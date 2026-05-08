# tests/test_price_feed.py
"""Aurus Sprint 1 — Stage 1 Tests: Price Feed
=============================================
Unit tests for src/data/price_feed.py.

MetaTrader5 is mocked so these tests run on Linux/CI without a live terminal.
The mock is injected into sys.modules BEFORE price_feed is imported, so the
module-level ``try: import MetaTrader5`` picks it up automatically.

Tests cover all 6 acceptance criteria from the Stage 1 build plan:
    1. connect() returns True with valid credentials
    2. get_latest_candles() returns a non-empty list
    3. Each candle dict contains all required keys
    4. All price values are floats greater than zero
    5. disconnect() runs without error
    6. is_connected() returns False after disconnect
"""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Build a minimal MetaTrader5 mock and inject into sys.modules BEFORE
# price_feed is imported, so its module-level import picks up the mock.
# ---------------------------------------------------------------------------

def _make_candle_array():
    """Return a one-row numpy recarray that matches the MT5 rates format."""
    dtype = np.dtype(
        [
            ("time", np.int64),
            ("open", np.float64),
            ("high", np.float64),
            ("low", np.float64),
            ("close", np.float64),
            ("tick_volume", np.int64),
            ("spread", np.int32),
            ("real_volume", np.int64),
        ]
    )
    return np.array(
        [(1_740_826_800, 2985.50, 2990.00, 2983.00, 2988.75, 1200, 1, 0)],
        dtype=dtype,
    )


def _make_mt5_mock() -> MagicMock:
    """Build a fully-configured MetaTrader5 mock object."""
    mock = MagicMock()
    mock.TIMEFRAME_M1 = 1
    mock.TIMEFRAME_M15 = 15
    mock.TIMEFRAME_H1 = 16385
    mock.initialize.return_value = True
    mock.login.return_value = True
    mock.last_error.return_value = (0, "Success")
    mock.account_info.return_value = MagicMock(login=12345, server="DemoServer")
    mock.copy_rates_from_pos.return_value = _make_candle_array()
    mock.copy_rates_range.return_value = _make_candle_array()
    return mock


# Inject before any import of price_feed
MT5 = _make_mt5_mock()
sys.modules.setdefault("MetaTrader5", MT5)

# Import price_feed — it will pick up the mock from sys.modules.
# Then forcibly patch the module-level `mt5` reference in case the real
# package was already imported (e.g. on Windows).
import src.data.price_feed as price_feed  # noqa: E402

price_feed.mt5 = MT5  # ensure the module uses our mock regardless of platform


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_mock():
    """Restore the mock to its default passing state after a test mutates it."""
    MT5.initialize.return_value = True
    MT5.login.return_value = True
    MT5.account_info.return_value = MagicMock(login=12345, server="DemoServer")
    MT5.copy_rates_from_pos.return_value = _make_candle_array()
    MT5.copy_rates_range.return_value = _make_candle_array()


# ---------------------------------------------------------------------------
# Test 1 — connect() returns True with valid credentials
# ---------------------------------------------------------------------------

class TestConnect:
    """Test 1: connect() returns True with valid (mocked) credentials."""

    def test_connect_returns_true_on_success(self):
        """connect() must return True when initialize and login both succeed."""
        result = price_feed.connect()
        assert result is True

    def test_connect_returns_false_when_initialize_fails(self):
        """connect() must return False (not raise) when mt5.initialize fails."""
        MT5.initialize.return_value = False
        result = price_feed.connect()
        assert result is False
        _reset_mock()

    def test_connect_returns_false_when_login_fails(self):
        """connect() must return False (not raise) when mt5.login fails."""
        MT5.login.return_value = False
        result = price_feed.connect()
        assert result is False
        _reset_mock()


# ---------------------------------------------------------------------------
# Test 2–4 — get_latest_candles()
# ---------------------------------------------------------------------------

class TestGetLatestCandles:
    """Tests 2–4: candle fetch, required keys, price values > 0."""

    def test_returns_non_empty_list(self):
        """Test 2: get_latest_candles() returns a non-empty list."""
        result = price_feed.get_latest_candles()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_candle_contains_required_keys(self):
        """Test 3: Each candle dict contains all required keys."""
        required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
        result = price_feed.get_latest_candles()
        for candle in result:
            missing = required - candle.keys()
            assert not missing, f"Candle is missing keys: {missing}"

    def test_price_values_are_floats_greater_than_zero(self):
        """Test 4: All price values are floats greater than zero."""
        result = price_feed.get_latest_candles()
        for candle in result:
            for key in ("open", "high", "low", "close"):
                assert isinstance(candle[key], float), f"{key} must be float"
                assert candle[key] > 0, f"{key} must be > 0"

    def test_returns_empty_list_when_mt5_returns_no_data(self):
        """get_latest_candles() returns [] when MT5 returns an empty array."""
        empty = np.array([], dtype=np.float64)
        MT5.copy_rates_from_pos.return_value = empty
        result = price_feed.get_latest_candles()
        assert result == []
        _reset_mock()

    def test_returns_none_after_all_retries_fail(self):
        """get_latest_candles() returns None when every retry returns None."""
        MT5.copy_rates_from_pos.return_value = None
        with patch("src.data.price_feed.time.sleep"):  # don't actually sleep
            result = price_feed.get_latest_candles()
        assert result is None
        _reset_mock()


# ---------------------------------------------------------------------------
# Test 5 — disconnect() runs without error
# ---------------------------------------------------------------------------

class TestDisconnect:
    """Test 5: disconnect() runs without error."""

    def test_disconnect_does_not_raise(self):
        """Test 5: disconnect() must complete without raising any exception."""
        try:
            price_feed.disconnect()
        except Exception as exc:
            pytest.fail(f"disconnect() raised an unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Test 6 — is_connected() returns False after disconnect
# ---------------------------------------------------------------------------

class TestIsConnected:
    """Test 6: is_connected() returns False after disconnect."""

    def test_is_connected_true_when_account_info_exists(self):
        """is_connected() returns True when MT5 reports an active account."""
        MT5.account_info.return_value = MagicMock(login=12345)
        assert price_feed.is_connected() is True

    def test_is_connected_false_after_disconnect(self):
        """Test 6: is_connected() returns False when account_info is None."""
        MT5.account_info.return_value = None
        assert price_feed.is_connected() is False
        _reset_mock()


# ---------------------------------------------------------------------------
# Historical data — bonus coverage
# ---------------------------------------------------------------------------

class TestGetHistoricalData:
    """Basic coverage for get_historical_data()."""

    def test_returns_non_empty_list(self):
        """get_historical_data() returns a non-empty list with default date range."""
        result = price_feed.get_historical_data()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_candle_contains_required_keys(self):
        """Each historical candle contains all required keys."""
        required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
        result = price_feed.get_historical_data()
        for candle in result:
            assert not (required - candle.keys())

    def test_returns_none_after_all_retries_fail(self):
        """get_historical_data() returns None when every retry returns None."""
        MT5.copy_rates_range.return_value = None
        with patch("src.data.price_feed.time.sleep"):
            result = price_feed.get_historical_data()
        assert result is None
        _reset_mock()
