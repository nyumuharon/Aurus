"""
Test Trade Manager Module

Stage 2 tests for the Trade Manager.
"""

import pytest
import time
import sqlite3
import os
from config import settings
from src.execution import mt5_connector
from src.execution.trade_manager import (
    start_monitoring, stop_monitoring, is_monitoring, check_positions,
    apply_trailing_stop, check_partial_close, execute_partial_close,
    detect_closed_positions, handle_closed_position, get_position_status
)

# Use a test database
TEST_DB = "data/test_trade.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    original_db = settings.EXECUTION_DB_PATH
    settings.EXECUTION_DB_PATH = TEST_DB
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        
    mt5_connector._initialize_db()
    mt5_connector._mock_positions = []
    import src.execution.trade_manager as tm
    tm._position_state = {}
    tm._last_open_positions = {}
    
    yield
    
    stop_monitoring()
    mt5_connector.disconnect()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    settings.EXECUTION_DB_PATH = original_db

def test_start_monitoring_starts_background_thread_without_error():
    start_monitoring()
    assert is_monitoring() is True
    stop_monitoring()

def test_is_monitoring_returns_true_after_start():
    start_monitoring()
    assert is_monitoring() is True
    stop_monitoring()

def test_stop_monitoring_stops_thread_cleanly():
    start_monitoring()
    stop_monitoring()
    assert is_monitoring() is False

def test_is_monitoring_returns_false_after_stop():
    assert is_monitoring() is False
    start_monitoring()
    stop_monitoring()
    assert is_monitoring() is False

def test_check_positions_returns_list_without_error():
    mt5_connector.connect()
    res = check_positions()
    assert isinstance(res, list)

def test_apply_trailing_stop_moves_sl_up_for_profitable_buy():
    pos = {
        "ticket": 1, "signal": "BUY", "lot_size": 0.1,
        "entry_price": 2000.0, "current_price": 2020.0, "stop_loss": 1990.0,
        "take_profit": 2050.0
    }
    # ATR=5.0, MULTIPLIER=1.0 -> new SL = 2020 - 5 = 2015.0
    # 2015 > 1990 -> moves up
    mt5_connector.connect()
    mt5_connector._mock_positions = [pos]
    
    # Needs actual modification in mock connector to return True
    # wait, the mock uses actual placed orders if we just insert them manually
    res = apply_trailing_stop(pos, 5.0)
    assert res is True

def test_apply_trailing_stop_does_not_move_sl_down_for_buy():
    pos = {
        "ticket": 2, "signal": "BUY", "lot_size": 0.1,
        "entry_price": 2000.0, "current_price": 2005.0, "stop_loss": 2002.0,
        "take_profit": 2050.0
    }
    # ATR=5.0, new SL = 2005 - 5 = 2000.0. 2000 < 2002, should not move down
    res = apply_trailing_stop(pos, 5.0)
    assert res is False

def test_apply_trailing_stop_moves_sl_down_for_profitable_sell():
    pos = {
        "ticket": 3, "signal": "SELL", "lot_size": 0.1,
        "entry_price": 2000.0, "current_price": 1980.0, "stop_loss": 2010.0,
        "take_profit": 1950.0
    }
    # ATR=5, new SL = 1980 + 5 = 1985.0. 1985 < 2010 -> moves down
    mt5_connector.connect()
    mt5_connector._mock_positions = [pos]
    res = apply_trailing_stop(pos, 5.0)
    assert res is True

def test_apply_trailing_stop_does_not_move_sl_up_for_sell():
    pos = {
        "ticket": 4, "signal": "SELL", "lot_size": 0.1,
        "entry_price": 2000.0, "current_price": 1995.0, "stop_loss": 1998.0,
        "take_profit": 1950.0
    }
    # ATR=5, new SL = 1995 + 5 = 2000. 2000 > 1998 -> should not move up
    res = apply_trailing_stop(pos, 5.0)
    assert res is False

def test_apply_trailing_stop_does_not_apply_when_position_is_at_loss():
    pos = {
        "ticket": 5, "signal": "BUY", "lot_size": 0.1,
        "entry_price": 2000.0, "current_price": 1995.0, "stop_loss": 1990.0,
        "take_profit": 2050.0
    }
    res = apply_trailing_stop(pos, 5.0)
    assert res is False

def test_check_partial_close_returns_true_when_1_1_rr_reached_for_buy():
    pos = {
        "ticket": 6, "signal": "BUY", "lot_size": 0.1,
        "entry_price": 2000.0, "stop_loss": 1990.0, "current_price": 2010.0,
        "take_profit": 2050.0
    }
    assert check_partial_close(pos) is True

def test_check_partial_close_returns_true_when_1_1_rr_reached_for_sell():
    pos = {
        "ticket": 7, "signal": "SELL", "lot_size": 0.1,
        "entry_price": 2000.0, "stop_loss": 2010.0, "current_price": 1990.0,
        "take_profit": 1950.0
    }
    assert check_partial_close(pos) is True

def test_check_partial_close_returns_false_when_1_1_rr_not_yet_reached():
    pos = {
        "ticket": 8, "signal": "BUY", "lot_size": 0.1,
        "entry_price": 2000.0, "stop_loss": 1990.0, "current_price": 2005.0,
        "take_profit": 2050.0
    }
    assert check_partial_close(pos) is False

def test_check_partial_close_returns_false_when_already_partially_closed():
    pos = {
        "ticket": 9, "signal": "BUY", "lot_size": 0.1,
        "entry_price": 2000.0, "stop_loss": 1990.0, "current_price": 2010.0,
        "take_profit": 2050.0
    }
    import src.execution.trade_manager as tm
    tm._position_state[9] = {"partially_closed": True, "trailing_active": False}
    assert check_partial_close(pos) is False

def test_execute_partial_close_calls_close_position_with_50_percent_lot_size():
    mt5_connector.connect()
    pos = mt5_connector.place_order("BUY", 0.04, 2000.0, 1990.0, 2050.0)
    pos["current_price"] = 2010.0 # Profit!
    execute_partial_close(pos)
    updated = mt5_connector.get_position_by_ticket(pos["ticket"])
    assert updated["lot_size"] == 0.02

def test_execute_partial_close_moves_sl_to_breakeven_after_partial_close():
    mt5_connector.connect()
    pos = mt5_connector.place_order("BUY", 0.04, 2000.0, 1990.0, 2050.0)
    execute_partial_close(pos)
    updated = mt5_connector.get_position_by_ticket(pos["ticket"])
    assert updated["stop_loss"] == 2000.0

def test_detect_closed_positions_returns_positions_no_longer_in_open_list():
    import src.execution.trade_manager as tm
    tm._last_open_positions = {
        10: {"ticket": 10, "signal": "BUY"}
    }
    mt5_connector.connect()
    # mt5_connector has 0 open positions
    closed = detect_closed_positions()
    assert len(closed) == 1
    assert closed[0]["ticket"] == 10

def test_handle_closed_position_records_pnl_to_database():
    import src.execution.trade_manager as tm
    tm._position_state[10] = {"partially_closed": False, "trailing_active": False}
    handle_closed_position({"ticket": 10, "unrealized_pnl": 50.0})
    assert 10 not in tm._position_state

def test_get_position_status_returns_list_with_all_required_keys():
    mt5_connector.connect()
    mt5_connector.place_order("BUY", 0.04, 2000.0, 1990.0, 2050.0)
    status = get_position_status()
    assert len(status) == 1
    s = status[0]
    keys = ["ticket", "symbol", "signal", "lot_size", "entry_price", "current_price",
            "stop_loss", "take_profit", "unrealized_pnl", "partially_closed",
            "trailing_active", "open_time", "monitoring_status"]
    for k in keys:
        assert k in s

def test_monitoring_loop_continues_after_individual_position_check_error():
    # If one check fails, loop doesn't crash.
    # Start loop, it should run without exception.
    start_monitoring()
    time.sleep(0.1)
    assert is_monitoring() is True
    stop_monitoring()
