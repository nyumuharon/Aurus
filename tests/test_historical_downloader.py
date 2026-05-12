import os
import shutil
import pytest
import pandas as pd
from datetime import datetime, timedelta

from src.data.historical_downloader import (
    create_directories,
    download_xauusd_1m,
    save_to_csv,
    load_from_csv
)
from config.settings import HISTORICAL_DATA_DIR, LSTM_SAVE_PATH

# Temporary directories for testing
TEST_HISTORICAL_DIR = "test_data/historical"
TEST_LSTM_DIR = "test_saved_models/lstm"

@pytest.fixture(autouse=True)
def mock_yf_download(monkeypatch):
    """Mock yf.download to instantly return empty dataframe, testing offline fallback without sleep delays."""
    monkeypatch.setattr("yfinance.download", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)



def test_create_directories(monkeypatch):
    """1. create_directories() creates all required folders"""
    monkeypatch.setattr("src.data.historical_downloader.HISTORICAL_DATA_DIR", TEST_HISTORICAL_DIR)
    monkeypatch.setattr("src.data.historical_downloader.LSTM_SAVE_PATH", f"{TEST_LSTM_DIR}/model.h5")
    monkeypatch.setattr("src.data.historical_downloader.TFT_SAVE_PATH", f"test_saved_models/tft/model.pt")
    monkeypatch.setattr("src.data.historical_downloader.RF_SAVE_PATH", f"test_saved_models/random_forest/model.pkl")
    
    create_directories()
    
    assert os.path.exists(TEST_HISTORICAL_DIR)
    assert os.path.exists(TEST_LSTM_DIR)
    assert os.path.exists("test_saved_models/tft")
    assert os.path.exists("test_saved_models/random_forest")
    
    # Cleanup
    shutil.rmtree("test_data", ignore_errors=True)
    shutil.rmtree("test_saved_models", ignore_errors=True)

def test_download_xauusd_1m_returns_dataframe():
    """2. download_xauusd_1m() returns a non-empty dataframe"""
    df = download_xauusd_1m(1)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty

def test_dataframe_columns():
    """3. Dataframe has correct columns"""
    df = download_xauusd_1m(1)
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    assert list(df.columns) == expected_cols
    assert df.index.name == 'timestamp'

def test_no_nan_values():
    """4. No NaN values in returned dataframe"""
    df = download_xauusd_1m(1)
    assert not df.isna().any().any()

def test_no_duplicate_timestamps():
    """5. No duplicate timestamps in returned dataframe"""
    df = download_xauusd_1m(1)
    assert not df.index.duplicated().any()

def test_save_to_csv(tmp_path):
    """6. save_to_csv() saves file to correct path"""
    df = pd.DataFrame({
        'open': [1.0], 'high': [1.0], 'low': [1.0], 'close': [1.0], 'volume': [1]
    }, index=pd.Index([datetime.now()], name='timestamp'))
    
    filepath = tmp_path / "test.csv"
    success = save_to_csv(df, str(filepath))
    
    assert success
    assert os.path.exists(filepath)

def test_load_from_csv(tmp_path):
    """7. load_from_csv() loads file and returns correct dataframe"""
    df = pd.DataFrame({
        'open': [1.0], 'high': [1.0], 'low': [1.0], 'close': [1.0], 'volume': [1]
    }, index=pd.Index([datetime.now()], name='timestamp'))
    
    filepath = tmp_path / "test.csv"
    save_to_csv(df, str(filepath))
    
    loaded_df = load_from_csv(str(filepath))
    assert loaded_df is not None
    assert not loaded_df.empty
    assert list(loaded_df.columns) == ['open', 'high', 'low', 'close', 'volume']

def test_data_spans_at_least_one_year():
    """8. Data spans at least 1 year"""
    df = download_xauusd_1m(1)
    span = df.index.max() - df.index.min()
    assert span.days >= 360  # Account for weekends/holidays slightly
