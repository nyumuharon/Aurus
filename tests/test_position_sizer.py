"""
Test Position Sizer Module

Stage 2 tests for the Position Sizer.
"""

import pytest
import math
from config import settings
from src.risk.position_sizer import (
    calculate_atr,
    calculate_lot_size,
    calculate_sl_tp,
    validate_risk_reward,
    get_position_parameters
)

@pytest.fixture
def sample_candles():
    # Provide 15 candles to compute 14 TR values for a 14-period ATR
    # Let's say high-low is 10 for all, so TR=10, ATR=10
    candles = []
    base_price = 2000.0
    for i in range(15):
        candles.append({
            "open": base_price,
            "high": base_price + 5,
            "low": base_price - 5,
            "close": base_price,
            "volume": 100
        })
    return candles

def test_calculate_atr_returns_correct_float(sample_candles):
    atr = calculate_atr(sample_candles, 14)
    assert atr == 10.0

def test_calculate_atr_returns_none_for_insufficient_candles():
    candles = [{"high": 1, "low": 0, "close": 0}] * 5
    assert calculate_atr(candles, 14) is None

def test_calculate_atr_returns_none_for_empty_candle_list():
    assert calculate_atr([], 14) is None

def test_calculate_lot_size_returns_correct_lot_for_known_inputs():
    # balance = 10000, risk_pct = 0.01 => risk_amount = 100
    # stop_loss_dist = 50.0 (e.g. 50 pips, pip_value=1.0)
    # lot = 100 / (50 * 1.0 / 0.01) = 100 / 5000 = 0.02
    assert calculate_lot_size(10000.0, 50.0) == 0.02

def test_calculate_lot_size_returns_minimum_lot_when_too_small():
    # If stop loss is huge, lot size would be < 0.01
    assert calculate_lot_size(1000.0, 10000.0) == 0.01

def test_calculate_lot_size_returns_maximum_lot_when_too_large():
    # If stop loss is tiny, lot size would be > 10.0
    assert calculate_lot_size(10000000.0, 1.0) == 10.0

def test_calculate_lot_size_returns_lot_rounded_to_correct_step_size():
    # step size = 0.01
    # expected 0.025 to round down to 0.02
    # risk = 100, sl_dist = 40 => lot = 100 / (40 * 100) = 0.025
    assert calculate_lot_size(10000.0, 40.0) == 0.02

def test_calculate_sl_tp_returns_correct_sl_below_entry_for_buy_signal():
    res = calculate_sl_tp("BUY", 100.0, 10.0)
    # SL multiplier = 1.5 => sl_dist = 15.0
    assert res["stop_loss"] == 85.0

def test_calculate_sl_tp_returns_correct_tp_above_entry_for_buy_signal():
    res = calculate_sl_tp("BUY", 100.0, 10.0)
    # TP multiplier = 3.0 => tp_dist = 30.0
    assert res["take_profit"] == 130.0

def test_calculate_sl_tp_returns_correct_sl_above_entry_for_sell_signal():
    res = calculate_sl_tp("SELL", 100.0, 10.0)
    assert res["stop_loss"] == 115.0

def test_calculate_sl_tp_returns_correct_tp_below_entry_for_sell_signal():
    res = calculate_sl_tp("SELL", 100.0, 10.0)
    assert res["take_profit"] == 70.0

def test_validate_risk_reward_returns_true_for_ratio_ge_2():
    assert validate_risk_reward(10.0, 20.0) is True

def test_validate_risk_reward_returns_false_for_ratio_lt_2():
    assert validate_risk_reward(10.0, 15.0) is False

def test_get_position_parameters_returns_dict_with_all_required_keys(sample_candles):
    res = get_position_parameters("BUY", 2000.0, sample_candles, 10000.0)
    required_keys = [
        "lot_size", "entry_price", "stop_loss", "take_profit",
        "stop_loss_distance", "take_profit_distance", "risk_reward",
        "atr", "risk_amount", "account_balance"
    ]
    for key in required_keys:
        assert key in res

def test_get_position_parameters_returns_none_when_atr_calculation_fails():
    res = get_position_parameters("BUY", 2000.0, [], 10000.0)
    assert res is None

def test_get_position_parameters_returns_none_when_rr_below_minimum(sample_candles, monkeypatch):
    monkeypatch.setattr(settings, "ATR_TP_MULTIPLIER", 1.0)
    res = get_position_parameters("BUY", 2000.0, sample_candles, 10000.0)
    assert res is None

def test_all_price_values_are_positive_floats(sample_candles):
    res = get_position_parameters("BUY", 2000.0, sample_candles, 10000.0)
    assert isinstance(res["entry_price"], float)
    assert isinstance(res["stop_loss"], float)
    assert isinstance(res["take_profit"], float)
    assert res["entry_price"] > 0
    assert res["stop_loss"] > 0
    assert res["take_profit"] > 0

def test_lot_size_is_always_multiple_of_lot_step(sample_candles):
    res = get_position_parameters("BUY", 2000.0, sample_candles, 10000.0)
    # Check if lot_size is a multiple of 0.01
    lot = res["lot_size"]
    # float math e.g. 0.02 / 0.01 = 2.0
    remainder = round((lot / 0.01) % 1, 5)
    assert remainder == 0.0 or remainder == 1.0
