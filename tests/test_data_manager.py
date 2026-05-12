# tests/test_data_manager.py
"""Aurus Sprint 1 — Stage 5 Tests: Data Manager
================================================
Unit tests for src/data/data_manager.py.

Tests cover all 8 acceptance criteria from the Stage 5 build plan:
    1. start() returns True with valid MT5 credentials
    2. is_ready() returns True after successful start
    3. get_market_snapshot() returns a dict
    4. Snapshot contains price, news, dxy, calendar, status keys
    5. status is one of OK, DEGRADED, or ERROR
    6. price.latest_candle contains all required OHLCV keys
    7. stop() runs without error
    8. is_ready() returns False after stop
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import src.data.data_manager as data_manager

# ---------------------------------------------------------------------------
# Setup and Teardown
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup():
    """Ensure data manager is stopped after each test."""
    yield
    data_manager.stop()


# ---------------------------------------------------------------------------
# Tests 1, 2, 7, 8 — Lifecycle (start, stop, is_ready)
# ---------------------------------------------------------------------------

@patch("src.data.data_manager.price_feed.connect", return_value=True)
@patch("src.data.data_manager.price_feed.disconnect")
@patch("src.data.data_manager.price_feed.is_connected", return_value=True)
class TestLifecycle:
    """Tests 1, 2, 7, 8: Lifecycle functions (start, stop, is_ready)."""

    def test_start_returns_true(self, mock_is_connected, mock_disconnect, mock_connect):
        """Test 1: start() returns True with valid MT5 credentials."""
        # mock internal update functions so they don't block or error
        with patch("src.data.data_manager._update_news"), \
             patch("src.data.data_manager._update_dxy"), \
             patch("src.data.data_manager._update_calendar"):
            
            result = data_manager.start()
            assert result is True
            assert mock_connect.called

    def test_is_ready_true_after_start(self, mock_is_connected, mock_disconnect, mock_connect):
        """Test 2: is_ready() returns True after successful start."""
        with patch("src.data.data_manager._update_news"), \
             patch("src.data.data_manager._update_dxy"), \
             patch("src.data.data_manager._update_calendar"):
            
            data_manager.start()
            assert data_manager.is_ready() is True

    def test_stop_runs_without_error(self, mock_is_connected, mock_disconnect, mock_connect):
        """Test 7: stop() runs without error."""
        with patch("src.data.data_manager._update_news"), \
             patch("src.data.data_manager._update_dxy"), \
             patch("src.data.data_manager._update_calendar"):
            
            data_manager.start()
            # If start() spun up the thread, we wait a moment
            time.sleep(0.1)
            data_manager.stop()
            assert mock_disconnect.called

    def test_is_ready_false_after_stop(self, mock_is_connected, mock_disconnect, mock_connect):
        """Test 8: is_ready() returns False after stop."""
        with patch("src.data.data_manager._update_news"), \
             patch("src.data.data_manager._update_dxy"), \
             patch("src.data.data_manager._update_calendar"):
            
            data_manager.start()
            data_manager.stop()
            assert data_manager.is_ready() is False


# ---------------------------------------------------------------------------
# Tests 3, 4, 5, 6 — Market Snapshot
# ---------------------------------------------------------------------------

@patch("src.data.data_manager.price_feed.get_latest_candles")
class TestGetMarketSnapshot:
    """Tests 3, 4, 5, 6: get_market_snapshot() structure and logic."""

    @pytest.fixture(autouse=True)
    def setup_state(self):
        """Mock the internal state of data manager before each test."""
        data_manager._latest_news = [{"headline": "Test News"}]
        data_manager._latest_dxy = {"timestamp": "2026", "price": 100.0, "trend": "BULLISH"}
        data_manager._todays_events = [{"event": "Test Event"}]
        with patch("src.data.calendar_feed.is_high_impact_window", return_value=False):
            yield

    def _mock_candles(self, *args, **kwargs):
        return [
            {
                "symbol": "XAUUSD",
                "timestamp": "2026-03-01 10:00:00",
                "open": 2000.0,
                "high": 2005.0,
                "low": 1995.0,
                "close": 2002.0,
                "volume": 100,
            }
        ]

    def test_returns_dict(self, mock_get_candles):
        """Test 3: get_market_snapshot() returns a dict."""
        mock_get_candles.side_effect = self._mock_candles
        result = data_manager.get_market_snapshot()
        assert isinstance(result, dict)

    def test_contains_required_keys(self, mock_get_candles):
        """Test 4: Snapshot contains price, news, dxy, calendar, status keys."""
        mock_get_candles.side_effect = self._mock_candles
        result = data_manager.get_market_snapshot()
        
        required = {"timestamp", "price", "news", "dxy", "calendar", "status"}
        for key in required:
            assert key in result

    def test_status_values(self, mock_get_candles):
        """Test 5: status is one of OK, DEGRADED, or ERROR."""
        # 1. OK status
        mock_get_candles.side_effect = self._mock_candles
        result = data_manager.get_market_snapshot()
        assert result["status"] == "OK"

        # 2. DEGRADED status (news missing)
        data_manager._latest_news = []
        result = data_manager.get_market_snapshot()
        assert result["status"] == "DEGRADED"
        
        # 3. ERROR status (price feed fails)
        mock_get_candles.side_effect = lambda *a, **kw: None
        result = data_manager.get_market_snapshot()
        assert result["status"] == "ERROR"

    def test_latest_candle_contains_keys(self, mock_get_candles):
        """Test 6: price.latest_candle contains all required OHLCV keys."""
        mock_get_candles.side_effect = self._mock_candles
        result = data_manager.get_market_snapshot()
        
        latest = result["price"]["latest_candle"]
        required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
        for key in required:
            assert key in latest

