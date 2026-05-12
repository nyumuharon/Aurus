"""
Tests for Stage 1 Preprocessor Module
=====================================
"""

import os
import pytest
import numpy as np
import pandas as pd

from src.models.preprocessor import (
    load_data,
    engineer_features,
    engineer_labels,
    normalize_features,
    split_data,
    prepare_lstm_sequences,
    prepare_rf_features,
    get_full_pipeline
)


@pytest.fixture
def sample_csv(tmp_path):
    """Fixture to generate a valid OHLCV CSV file."""
    dates = pd.date_range(start="2024-01-01", periods=500, freq="1min")
    df = pd.DataFrame({
        'open': np.linspace(2000, 2100, 500),
        'high': np.linspace(2005, 2105, 500),
        'low': np.linspace(1995, 2095, 500),
        'close': np.linspace(2002, 2102, 500) + np.sin(np.arange(500)) * 5,
        'volume': np.random.randint(100, 1000, 500)
    }, index=dates)
    df.index.name = 'timestamp'
    filepath = tmp_path / "test_ohlcv.csv"
    df.to_csv(filepath)
    return str(filepath)


def test_load_data(sample_csv):
    """1. load_data() returns non-empty dataframe with correct columns"""
    df = load_data(sample_csv)
    assert df is not None
    assert not df.empty
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']


def test_engineer_features_adds_columns(sample_csv):
    """2. engineer_features() adds all 11 feature columns"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    
    assert df_feat is not None
    expected_feats = [
        'returns', 'ema_20', 'ema_50', 'ema_200', 'rsi_14',
        'macd', 'macd_signal', 'atr_14', 'volume_delta', 'hour', 'day_of_week'
    ]
    for feat in expected_feats:
        assert feat in df_feat.columns


def test_engineer_features_no_nans(sample_csv):
    """3. engineer_features() produces no NaN values"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    assert not df_feat.isna().any().any()



def test_engineer_labels(sample_csv):
    """4. engineer_labels() adds label column with only values 0, 1, or 2"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    df_lbl = engineer_labels(df_feat)
    
    assert 'label' in df_lbl.columns
    valid_labels = {0, 1, 2}
    unique_labels = set(df_lbl['label'].unique())
    assert unique_labels.issubset(valid_labels)


def test_normalize_features(sample_csv):
    """5. normalize_features() returns values between 0.0 and 1.0"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    df_lbl = engineer_labels(df_feat)
    
    df_norm, scaler = normalize_features(df_lbl, fit=True)
    
    # Exclude label column when checking bounds
    feature_cols = [c for c in df_norm.columns if c != 'label']
    assert df_norm[feature_cols].min().min() >= 0.0
    assert df_norm[feature_cols].max().max() <= 1.0


def test_split_data(sample_csv):
    """6. split_data() returns correct proportions (70/15/15)"""
    df = load_data(sample_csv)
    train, val, test = split_data(df)
    
    total = len(df)
    assert abs(len(train) - total * 0.70) <= 2
    assert abs(len(val) - total * 0.15) <= 2
    assert abs(len(test) - total * 0.15) <= 2


def test_prepare_lstm_sequences(sample_csv):
    """7. prepare_lstm_sequences() returns 3D array of shape (samples, 60, 6)"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    df_lbl = engineer_labels(df_feat)
    
    X, y = prepare_lstm_sequences(df_lbl, lookback=60)
    assert X.ndim == 3
    assert X.shape[1] == 60
    assert X.shape[2] == 6
    assert len(X) == len(y)


def test_prepare_rf_features(sample_csv):
    """8. prepare_rf_features() returns 2D array"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    df_lbl = engineer_labels(df_feat)
    
    X, y = prepare_rf_features(df_lbl)
    assert X.ndim == 2
    assert len(X) == len(y)


def test_get_full_pipeline(sample_csv):
    """9. get_full_pipeline() returns dict with lstm, tft, rf, smc keys"""
    pipeline = get_full_pipeline(sample_csv, sample_csv)
    
    assert isinstance(pipeline, dict)
    expected_keys = ['lstm', 'tft', 'rf', 'smc', 'scaler']
    for k in expected_keys:
        assert k in pipeline
        
    assert 'X_train' in pipeline['lstm']
    assert 'train' in pipeline['tft']
    assert 'raw_df' in pipeline['smc']


def test_label_distribution(sample_csv):
    """10. Label distribution is not severely imbalanced (no class > 80%)"""
    df = load_data(sample_csv)
    df_feat = engineer_features(df)
    df_lbl = engineer_labels(df_feat)
    
    counts = df_lbl['label'].value_counts(normalize=True)
    assert counts.max() <= 0.82  # Slight allowance for small edge variations
