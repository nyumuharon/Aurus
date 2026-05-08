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
