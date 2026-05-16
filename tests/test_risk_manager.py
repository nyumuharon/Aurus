"""
Test Risk Manager Module

Stage 1 tests for the Risk Manager.
"""

import pytest
import sqlite3
import os
from datetime import datetime
from config import settings
from src.risk.risk_manager import (
    initialize_db,
    get_daily_stats,
    get_total_drawdown,
    check_daily_loss,
    check_total_drawdown,
    check_trade_count,
    check_high_impact_window,
    get_default_block,
    record_trade_open,
    record_trade_close,
    evaluate
)

# Use a test database
TEST_DB = "data/test_risk.db"

@pytest.fixture(autouse=True)
def setup_test_db():
    original_db = settings.RISK_DB_PATH
    settings.RISK_DB_PATH = TEST_DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    initialize_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    settings.RISK_DB_PATH = original_db

def test_initialize_db_creates_required_tables_without_error():
    with sqlite3.connect(TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_summary'")
        assert cursor.fetchone() is not None

def test_get_daily_stats_returns_dict_with_trade_count_and_daily_pnl_keys():
    stats = get_daily_stats()
    assert "trade_count" in stats
    assert "daily_pnl" in stats

def test_get_daily_stats_returns_zero_values_on_fresh_day():
    stats = get_daily_stats()
    assert stats["trade_count"] == 0
    assert stats["daily_pnl"] == 0.0

def test_check_daily_loss_returns_true_when_daily_loss_is_below_limit():
    assert check_daily_loss(-100.0) is True

def test_check_daily_loss_returns_false_when_daily_loss_exceeds_5_percent():
    assert check_daily_loss(-600.0) is False

def test_check_total_drawdown_returns_true_when_drawdown_is_below_limit():
    assert check_total_drawdown(0.05) is True

def test_check_total_drawdown_returns_false_when_drawdown_exceeds_10_percent():
    assert check_total_drawdown(0.15) is False

def test_check_trade_count_returns_true_when_count_is_below_max():
    assert check_trade_count(2) is True

def test_check_trade_count_returns_false_when_count_reaches_max():
    assert check_trade_count(3) is False

def test_check_high_impact_window_returns_true_when_no_high_impact_events():
    assert check_high_impact_window({"high_impact_window": False}) is True

def test_check_high_impact_window_returns_false_when_high_impact_event_imminent():
    assert check_high_impact_window({"high_impact_window": True}) is False

@pytest.fixture
def passing_validation_result():
    return {
        "timestamp": "2026-03-01 10:00:00",
        "signal": "BUY",
        "validated": True,
        "decision": "YES",
        "reason": "AI agreed"
    }

@pytest.fixture
def passing_market_snapshot():
    candles = []
    base_price = 2988.75
    for i in range(15):
        candles.append({
            "open": base_price,
            "high": base_price + 5,
            "low": base_price - 5,
            "close": base_price,
            "volume": 100
        })
    return {
        "price": {
            "latest_candle": {"close": 2988.75},
            "candles_1m": candles
        },
        "calendar": {
            "high_impact_window": False
        }
    }

def test_evaluate_returns_approved_dict_when_all_checks_pass(passing_validation_result, passing_market_snapshot):
    result = evaluate(passing_validation_result, passing_market_snapshot)
    assert result["decision"] == "APPROVED"
    assert result["passed_to_execution"] is True

def test_evaluate_returns_blocked_when_validation_result_validated_is_false(passing_validation_result, passing_market_snapshot):
    passing_validation_result["validated"] = False
    result = evaluate(passing_validation_result, passing_market_snapshot)
    assert result["decision"] == "BLOCKED"

def test_evaluate_returns_blocked_when_daily_loss_limit_is_breached(passing_validation_result, passing_market_snapshot):
    with sqlite3.connect(TEST_DB) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("UPDATE daily_summary SET daily_pnl = ? WHERE date = ?", (-600.0, today))
        conn.commit()
    result = evaluate(passing_validation_result, passing_market_snapshot)
    assert result["decision"] == "BLOCKED"

def test_evaluate_returns_blocked_when_total_drawdown_is_breached(passing_validation_result, passing_market_snapshot):
    with sqlite3.connect(TEST_DB) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("UPDATE daily_summary SET peak_balance = 10000, close_balance = 8000 WHERE date = ?", (today,))
        conn.commit()
    result = evaluate(passing_validation_result, passing_market_snapshot)
    assert result["decision"] == "BLOCKED"

def test_evaluate_returns_blocked_when_max_trades_reached(passing_validation_result, passing_market_snapshot):
    with sqlite3.connect(TEST_DB) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("UPDATE daily_summary SET trade_count = 3 WHERE date = ?", (today,))
        conn.commit()
    result = evaluate(passing_validation_result, passing_market_snapshot)
    assert result["decision"] == "BLOCKED"

def test_evaluate_returns_blocked_when_high_impact_event_imminent(passing_validation_result, passing_market_snapshot):
    passing_market_snapshot["calendar"]["high_impact_window"] = True
    result = evaluate(passing_validation_result, passing_market_snapshot)
    assert result["decision"] == "BLOCKED"

def test_record_trade_open_writes_to_trades_table_without_error():
    record_trade_open("TEST-123", "BUY", 0.1, 2900.0, 2890.0, 2920.0)
    with sqlite3.connect(TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE trade_id = 'TEST-123'")
        assert cursor.fetchone() is not None

def test_record_trade_close_updates_trade_record_and_daily_pnl_correctly():
    record_trade_open("TEST-123", "BUY", 0.1, 2900.0, 2890.0, 2920.0)
    record_trade_close("TEST-123", 2910.0, 100.0)
    with sqlite3.connect(TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, pnl FROM trades WHERE trade_id = 'TEST-123'")
        row = cursor.fetchone()
        assert row[0] == "CLOSED"
        assert row[1] == 100.0
        
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT daily_pnl FROM daily_summary WHERE date = ?", (today,))
        daily = cursor.fetchone()
        assert daily[0] == 100.0

def test_get_default_block_returns_correct_structure():
    block = get_default_block("test")
    assert block["decision"] == "BLOCKED"
    assert block["passed_to_execution"] is False
    assert block["reason"] == "test"
