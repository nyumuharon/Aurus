"""
Tests for Stage 3 TFT Model Module
==================================
"""

import os
import pytest
import numpy as np
import pandas as pd

from config import settings
from src.models import tft_model


@pytest.fixture(scope="module", autouse=True)
def setup_tft_test_env(tmp_path_factory):
    """Setup safe module environment paths for TFT model testing."""
    fn = tmp_path_factory.mktemp("saved_models") / "tft" / "tft_model.pt"
    filepath = str(fn)
    settings.TFT_SAVE_PATH = filepath
    settings.TFT_EPOCHS = 1
    settings.TFT_BATCH_SIZE = 4
    
    # Generate mock dataframe
    dates = pd.date_range(start="2024-01-01", periods=100, freq="15min")
    df = pd.DataFrame({
        'open': np.linspace(2000, 2100, 100),
        'high': np.linspace(2005, 2105, 100),
        'low': np.linspace(1995, 2095, 100),
        'close': np.linspace(2002, 2102, 100),
        'volume': np.random.randint(100, 1000, 100),
        'time_idx': range(100),
        'group_id': 'XAUUSD',
        'label': 1
    }, index=dates)
    
    ds = tft_model.prepare_dataset(df)
    tft_model.train(ds, ds)


def test_prepare_dataset_returns_valid():
    """1. prepare_dataset() returns a TimeSeriesDataSet without error"""
    df = pd.DataFrame({
        'open': [2000.0]*10, 'high': [2005.0]*10, 'low': [1995.0]*10, 'close': [2002.0]*10, 'volume': [100]*10,
        'time_idx': range(10), 'group_id': ['XAUUSD']*10, 'label': [1]*10
    })
    ds = tft_model.prepare_dataset(df)
    assert ds is not None


def test_build_model_instance():
    """2. build_model() returns a TFT model instance"""
    df = pd.DataFrame({
        'open': [2000.0]*10, 'high': [2005.0]*10, 'low': [1995.0]*10, 'close': [2002.0]*10, 'volume': [100]*10,
        'time_idx': range(10), 'group_id': ['XAUUSD']*10, 'label': [1]*10
    })
    ds = tft_model.prepare_dataset(df)
    model = tft_model.build_model(ds)
    assert model is not None
    assert hasattr(model, 'output_shape') or hasattr(model, 'predict') or hasattr(model, 'forward')


def test_train_completes():
    """3. train() completes without error on small synthetic dataset"""
    df = pd.DataFrame({
        'open': [2000.0]*10, 'high': [2005.0]*10, 'low': [1995.0]*10, 'close': [2002.0]*10, 'volume': [100]*10,
        'time_idx': range(10), 'group_id': ['XAUUSD']*10, 'label': [1]*10
    })
    ds = tft_model.prepare_dataset(df)
    # File already exists from module setup, skipping/running instantly
    tft_model.train(ds, ds)


def test_model_file_saved():
    """4. Model file saved to correct path after training"""
    assert os.path.exists(settings.TFT_SAVE_PATH)


def test_load_model_without_error():
    """5. load_model() loads saved model without error"""
    model = tft_model.load_model()
    assert model is not None


def test_predict_returns_dict():
    """6. predict() returns dict with signal, confidence, probabilities keys"""
    df = pd.DataFrame({'close': [2000.0]})
    res = tft_model.predict(df)
    assert res is not None
    assert isinstance(res, dict)
    for k in ["model", "signal", "confidence", "probabilities"]:
        assert k in res


def test_predict_signal_value():
    """7. signal is one of BULLISH, BEARISH, or NEUTRAL"""
    df = pd.DataFrame({'close': [2000.0]})
    res = tft_model.predict(df)
    assert res["signal"] in {"BULLISH", "BEARISH", "NEUTRAL"}


def test_predict_confidence_range():
    """8. confidence is float between 0.0 and 1.0"""
    df = pd.DataFrame({'close': [2000.0]})
    res = tft_model.predict(df)
    assert isinstance(res["confidence"], float)
    assert 0.0 <= res["confidence"] <= 1.0


def test_predict_probabilities_sum():
    """9. probabilities sum to approximately 1.0"""
    df = pd.DataFrame({'close': [2000.0]})
    res = tft_model.predict(df)
    probs = res["probabilities"]
    assert abs(sum(probs.values()) - 1.0) < 1e-4


def test_get_signal_valid():
    """10. get_signal() returns valid signal dict"""
    res = tft_model.get_signal()
    assert res is not None
    assert isinstance(res, dict)
    assert res["model"] == "tft"
    assert res["signal"] in {"BULLISH", "BEARISH", "NEUTRAL"}
