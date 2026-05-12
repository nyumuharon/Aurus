"""
Tests for Stage 2 LSTM Model Module
===================================
"""

import os
import pytest
import numpy as np

from config import settings
from src.models import lstm_model


@pytest.fixture(scope="module", autouse=True)
def setup_module_test_model(tmp_path_factory):
    """Ensure a trained model file exists once for the whole test module."""
    # Use module scope to prevent re-training for every single test function
    fn = tmp_path_factory.mktemp("saved_models") / "lstm" / "lstm_model.h5"
    filepath = str(fn)
    
    # Store original settings to restore later if needed, but pytest processes are isolated
    settings.LSTM_SAVE_PATH = filepath
    settings.LSTM_EPOCHS = 1
    settings.LSTM_BATCH_SIZE = 8
    
    # Train once to create the file
    X_train = np.random.random((8, 60, 6)).astype(np.float32)
    y_train = np.random.randint(0, 3, size=(8,)).astype(np.float32)
    lstm_model.train(X_train, y_train, X_train, y_train)


def test_build_model_compiled():
    """1. build_model() returns a compiled Keras model"""
    import tensorflow as tf
    model = lstm_model.build_model((60, 6))
    assert isinstance(model, tf.keras.Model)
    assert model.optimizer is not None
    assert model.loss == 'sparse_categorical_crossentropy'


def test_model_input_shape():
    """2. Model input shape is (None, 60, 6)"""
    model = lstm_model.build_model((60, 6))
    assert model.input_shape == (None, 60, 6)


def test_model_output_shape():
    """3. Model output shape is (None, 3)"""
    model = lstm_model.build_model((60, 6))
    assert model.output_shape == (None, 3)


def test_train_completes():
    """4. train() completes without error on small synthetic dataset"""
    # Since file already exists from module setup, train skips instantly or runs safely
    X = np.random.random((8, 60, 6)).astype(np.float32)
    y = np.random.randint(0, 3, size=(8,)).astype(np.float32)
    res = lstm_model.train(X, y, X, y)
    # Returns None if skipped, or history if trained
    assert res is None or hasattr(res, 'history')


def test_model_file_saved():
    """5. Model file is saved to correct path after training"""
    assert os.path.exists(settings.LSTM_SAVE_PATH)


def test_load_model():
    """6. load_model() loads saved model without error"""
    model = lstm_model.load_model()
    assert model is not None
    assert model.output_shape == (None, 3)


def test_predict_returns_dict():
    """7. predict() returns dict with signal, confidence, probabilities keys"""
    single_window = np.random.random((60, 6)).astype(np.float32)
    res = lstm_model.predict(single_window)
    
    assert res is not None
    assert isinstance(res, dict)
    for k in ["model", "signal", "confidence", "probabilities"]:
        assert k in res


def test_predict_signal_value():
    """8. signal value is one of BUY, SELL, or HOLD"""
    single_window = np.random.random((60, 6)).astype(np.float32)
    res = lstm_model.predict(single_window)
    assert res["signal"] in {"BUY", "SELL", "HOLD"}


def test_predict_confidence_range():
    """9. confidence is a float between 0.0 and 1.0"""
    single_window = np.random.random((60, 6)).astype(np.float32)
    res = lstm_model.predict(single_window)
    conf = res["confidence"]
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0


def test_predict_probabilities_sum():
    """10. probabilities sum to approximately 1.0"""
    single_window = np.random.random((60, 6)).astype(np.float32)
    res = lstm_model.predict(single_window)
    probs = res["probabilities"]
    assert abs(sum(probs.values()) - 1.0) < 1e-4
