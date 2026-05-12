"""
Tests for Stage 4 Random Forest Module
======================================
"""

import os
import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from config import settings
from src.models import random_forest


@pytest.fixture(scope="module", autouse=True)
def setup_rf_test_env(tmp_path_factory):
    """Setup safe module environment paths and fast small ensemble parameters."""
    fn = tmp_path_factory.mktemp("saved_models") / "random_forest" / "rf_model.pkl"
    filepath = str(fn)
    settings.RF_SAVE_PATH = filepath
    settings.RF_ESTIMATORS = 2
    
    # Train once to create model file
    X = np.random.random((20, 11))
    y = np.random.randint(0, 3, size=(20,))
    random_forest.train(X, y)


def test_build_model_instance():
    """1. build_model() returns a RandomForestClassifier instance"""
    model = random_forest.build_model()
    assert isinstance(model, RandomForestClassifier)


def test_train_completes():
    """2. train() completes without error on synthetic dataset"""
    X = np.random.random((10, 11))
    y = np.random.randint(0, 3, size=(10,))
    # File exists, skips/runs safely
    random_forest.train(X, y)


def test_model_file_saved():
    """3. Model saved to correct path after training"""
    assert os.path.exists(settings.RF_SAVE_PATH)


def test_load_model_without_error():
    """4. load_model() loads saved model without error"""
    model = random_forest.load_model()
    assert model is not None
    assert hasattr(model, 'predict_proba')


def test_predict_returns_dict():
    """5. predict() returns dict with signal, confidence, probabilities keys"""
    row = np.random.random((1, 11))
    res = random_forest.predict(row)
    assert res is not None
    assert isinstance(res, dict)
    for k in ["model", "signal", "confidence", "probabilities"]:
        assert k in res


def test_predict_signal_value():
    """6. signal is one of BUY, SELL, or HOLD"""
    row = np.random.random((1, 11))
    res = random_forest.predict(row)
    assert res["signal"] in {"BUY", "SELL", "HOLD"}


def test_predict_confidence_range():
    """7. confidence is float between 0.0 and 1.0"""
    row = np.random.random((1, 11))
    res = random_forest.predict(row)
    assert isinstance(res["confidence"], float)
    assert 0.0 <= res["confidence"] <= 1.0


def test_predict_probabilities_sum():
    """8. probabilities sum to approximately 1.0"""
    row = np.random.random((1, 11))
    res = random_forest.predict(row)
    probs = res["probabilities"]
    assert abs(sum(probs.values()) - 1.0) < 1e-4


def test_get_feature_importance_keys():
    """9. get_feature_importance() returns dict with all feature names"""
    importances = random_forest.get_feature_importance()
    assert importances is not None
    assert isinstance(importances, dict)
    
    expected_feats = [
        'returns', 'ema_20', 'ema_50', 'ema_200', 'rsi_14',
        'macd', 'macd_signal', 'atr_14', 'volume_delta', 'hour', 'day_of_week'
    ]
    for feat in expected_feats:
        assert feat in importances


def test_feature_importance_sum():
    """10. Feature importances sum to approximately 1.0"""
    importances = random_forest.get_feature_importance()
    assert abs(sum(importances.values()) - 1.0) < 1e-4
