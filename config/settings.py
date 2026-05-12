# config/settings.py
# Aurus system configuration constants
# Never commit real credentials to GitHub

# MetaTrader 5
MT5_LOGIN = 0                        # Replace with your MT5 account number
MT5_PASSWORD = ""                    # Replace with your MT5 password
MT5_SERVER = ""                      # Replace with your broker server name

# Symbol
SYMBOL = "XAUUSD"
TIMEFRAME_1M = None                  # Will be set after MT5 import
TIMEFRAME_15M = None
TIMEFRAME_1H = None

# News API
NEWS_API_KEY = ""                    # Replace with your NewsAPI key
NEWS_FETCH_INTERVAL_SECONDS = 300    # Every 5 minutes

# Risk constants (used later in Sprint 4)
MAX_DAILY_LOSS_PCT = 0.05
MAX_TOTAL_DRAWDOWN_PCT = 0.10
MAX_TRADES_PER_DAY = 3
RISK_PER_TRADE_PCT = 0.01

# Logging
LOG_FILE = "logs/aurus.log"
LOG_LEVEL = "INFO"

# Ollama
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434"

# Historical data
HISTORICAL_DATA_DIR = "data/historical"
XAUUSD_1M_FILE = "data/historical/XAUUSD_1M.csv"
XAUUSD_15M_FILE = "data/historical/XAUUSD_15M.csv"
HISTORICAL_YEARS = 2

# Model save paths
LSTM_SAVE_PATH = "saved_models/lstm/lstm_model.h5"
TFT_SAVE_PATH = "saved_models/tft/tft_model.pt"
RF_SAVE_PATH = "saved_models/random_forest/rf_model.pkl"

# LSTM architecture
LSTM_LOOKBACK = 60           # candles to look back
LSTM_FEATURES = 6            # OHLCV + volume
LSTM_UNITS_1 = 64
LSTM_UNITS_2 = 32
LSTM_DROPOUT = 0.2
LSTM_EPOCHS = 50
LSTM_BATCH_SIZE = 32

# TFT
TFT_LOOKBACK = 200
TFT_FEATURES = 10
TFT_EPOCHS = 30
TFT_BATCH_SIZE = 16

# Random Forest
RF_ESTIMATORS = 200
RF_JOBS = -1                 # use all CPU cores

# Ensemble weights
ENSEMBLE_WEIGHTS = {
    "lstm": 0.30,
    "tft": 0.30,
    "random_forest": 0.20,
    "smc_detector": 0.20
}
ENSEMBLE_THRESHOLD = 0.60    # minimum confidence to generate signal

# Training split
TRAIN_SPLIT = 0.70
VALIDATION_SPLIT = 0.15
TEST_SPLIT = 0.15
