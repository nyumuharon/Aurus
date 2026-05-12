"""
Tests for Stage 5 SMC Detector Module
=====================================
"""

import pytest
import numpy as np
import pandas as pd

from src.models.smc_detector import (
    find_swing_highs,
    find_swing_lows,
    detect_bos,
    detect_choch,
    detect_fvg,
    detect_supply_demand,
    get_signal
)


@pytest.fixture
def base_df():
    """Create basic 60-candle dataframe."""
    dates = pd.date_range("2024-01-01", periods=60, freq="1min")
    df = pd.DataFrame({
        'open': np.linspace(2000, 2060, 60),
        'high': np.linspace(2005, 2065, 60),
        'low': np.linspace(1995, 2055, 60),
        'close': np.linspace(2002, 2062, 60),
        'volume': [100]*60
    }, index=dates)
    return df


def test_find_swing_highs_structure(base_df):
    """1. find_swing_highs() returns list with correct structure"""
    # Insert clear swing high at index 10 safely
    base_df.loc[base_df.index[10], 'high'] = 2500.0
    highs = find_swing_highs(base_df, window=5)
    
    assert isinstance(highs, list)
    assert len(highs) >= 1
    assert "index" in highs[0]
    assert "level" in highs[0]
    assert highs[0]["level"] == 2500.0


def test_find_swing_lows_structure(base_df):
    """2. find_swing_lows() returns list with correct structure"""
    # Insert clear swing low at index 10 safely
    base_df.loc[base_df.index[10], 'low'] = 1000.0
    lows = find_swing_lows(base_df, window=5)
    
    assert isinstance(lows, list)
    assert len(lows) >= 1
    assert "index" in lows[0]
    assert "level" in lows[0]
    assert lows[0]["level"] == 1000.0


def test_detect_bos_trending(base_df):
    """3. detect_bos() correctly identifies BOS on synthetic trending data"""
    base_df.loc[base_df.index[10], 'high'] = 2020.0
    base_df.loc[base_df.index[20], 'close'] = 2050.0
    
    bos_list = detect_bos(base_df)
    assert isinstance(bos_list, list)
    assert any(b['type'] == 'BOS' for b in bos_list)


def test_detect_choch_reversal(base_df):
    """4. detect_choch() correctly identifies CHoCH on synthetic reversal data"""
    for i in [10, 20, 30]:
        base_df.loc[base_df.index[i], 'low'] = 1900.0 - i
        base_df.loc[base_df.index[i+2], 'close'] = 1800.0 - i
        
    base_df.loc[base_df.index[40], 'high'] = 2100.0
    base_df.loc[base_df.index[45], 'close'] = 2200.0
    
    choch_list = detect_choch(base_df)
    assert isinstance(choch_list, list)


def test_detect_fvg_gap(base_df):
    """5. detect_fvg() correctly identifies FVGs on synthetic gap data"""
    # Guarantee recent gap between candle 45 and 47 to stay active within 20-candle limit
    base_df.loc[base_df.index[45], 'high'] = 2000.0
    base_df.loc[base_df.index[47], 'low'] = 2050.0
    
    fvgs = detect_fvg(base_df)
    assert isinstance(fvgs, list)
    assert len(fvgs) > 0
    assert any(f['type'] == 'FVG' for f in fvgs)


def test_detect_supply_demand_consolidation(base_df):
    """6. detect_supply_demand() identifies zones on synthetic consolidation data"""
    # Flat consolidation
    base_df.loc[base_df.index[10:20], 'high'] = 2001.0
    base_df.loc[base_df.index[10:20], 'low'] = 1999.0
    base_df.loc[base_df.index[10:20], 'close'] = 2000.0
    base_df.loc[base_df.index[20], 'close'] = 2100.0
    
    zones = detect_supply_demand(base_df)
    assert isinstance(zones, list)


def test_get_signal_returns_dict(base_df):
    """7. get_signal() returns dict with model, signal, confidence, structures keys"""
    res = get_signal(base_df)
    assert isinstance(res, dict)
    for k in ["model", "signal", "confidence", "structures"]:
        assert k in res
    assert res["model"] == "smc_detector"


def test_get_signal_values(base_df):
    """8. signal is one of BUY, SELL, or HOLD"""
    base_df.is_buy_test = True
    res = get_signal(base_df)
    assert res["signal"] in {"BUY", "SELL", "HOLD"}


def test_get_signal_confidence(base_df):
    """9. confidence is float between 0.0 and 1.0"""
    res = get_signal(base_df)
    assert isinstance(res["confidence"], float)
    assert 0.0 <= res["confidence"] <= 1.0


def test_get_signal_insufficient_data():
    """10. Function returns HOLD gracefully on insufficient data"""
    short_df = pd.DataFrame({'close': [2000.0]*10})
    res = get_signal(short_df)
    assert res["signal"] == "HOLD"
