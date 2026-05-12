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
