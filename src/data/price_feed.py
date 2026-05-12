# src/data/price_feed.py
"""Aurus Sprint 1 — Stage 1: MetaTrader 5 Price Feed
====================================================
Connects to MetaTrader 5 and provides live and historical OHLCV data for
XAU/USD. This is the primary data source for all pattern detection models
in Sprint 2.

Rules:
- All credentials come from config/settings.py — never hardcoded here.
- All errors are logged via the Python logging module — never use print().
- Data fetch failures retry up to 3 times with a 2-second delay.
"""

import logging
import os
import time
from datetime import datetime, timedelta

# MetaTrader5 is a Windows-only package. On Linux, we try to use the unofficial
# mt5linux bridge. If both fail, mt5 is set to None for safe fallback values.
try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:
    try:
        from mt5linux import MetaTrader5
        # The mt5linux package requires us to instantiate the class to use it
        # as a drop-in module replacement. It assumes the server is running.
        mt5 = MetaTrader5()  # type: ignore[assignment]
    except Exception:
        mt5 = None  # type: ignore[assignment]


from config import settings

# ---------------------------------------------------------------------------
# Logging setup — writes to the path defined in settings.LOG_FILE
# ---------------------------------------------------------------------------
_log_dir = os.path.dirname(settings.LOG_FILE)
if _log_dir:
    os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    filename=settings.LOG_FILE,
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------
_RETRY_COUNT = 3
_RETRY_DELAY = 2  # seconds


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _candles_to_dicts(symbol: str, raw) -> list:
    """Convert an MT5 rates recarray into the standard Aurus candle format.

    Args:
        symbol: Trading symbol string, e.g. ``"XAUUSD"``.
        raw:    Numpy recarray returned by ``mt5.copy_rates_*``.

    Returns:
        List of candle dicts with keys: symbol, timestamp, open, high,
        low, close, volume.
    """
    result = []
    for row in raw:
        result.append(
            {
                "symbol": symbol,
                "timestamp": datetime.utcfromtimestamp(int(row["time"])).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["tick_volume"]),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def connect() -> bool:
    """Connect to the MetaTrader 5 terminal using credentials from settings.py.

    Returns:
        True  — connection established successfully.
        False — connection failed; error is logged, no exception raised.
    """
    if mt5 is None:
        logger.error("MetaTrader5 package is not installed (Linux/CI environment).")
        return False

    if not mt5.initialize():
        logger.error("mt5.initialize() failed: %s", mt5.last_error())
        return False

    authorised = mt5.login(
        login=settings.MT5_LOGIN,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    )
    if not authorised:
        logger.error(
            "MT5 login failed for account %s on server '%s': %s",
            settings.MT5_LOGIN,
            settings.MT5_SERVER,
            mt5.last_error(),
        )
        mt5.shutdown()
        return False

    logger.info(
        "MT5 connected — account %s on server '%s'.",
        settings.MT5_LOGIN,
        settings.MT5_SERVER,
    )
    return True


def disconnect() -> None:
    """Cleanly shut down the MetaTrader 5 connection.

    Safe to call even if MT5 is not connected or the package is unavailable.
    """
    if mt5 is None:
        return
    mt5.shutdown()
    logger.info("MT5 connection closed.")


def is_connected() -> bool:
    """Check whether the MetaTrader 5 connection is currently alive.

    Returns:
        True  — terminal is reachable and the account is authorised.
        False — not connected, or MT5 package unavailable.
    """
    if mt5 is None:
        return False
    return mt5.account_info() is not None


def get_latest_candles(
    symbol: str = settings.SYMBOL,
    timeframe=None,
    count: int = 100,
):
    """Fetch the last *count* OHLCV candles for *symbol* on *timeframe*.

    Retries up to 3 times with a 2-second delay between attempts.

    Args:
        symbol:    Trading symbol (default: settings.SYMBOL → ``"XAUUSD"``).
        timeframe: MT5 timeframe constant. Defaults to ``mt5.TIMEFRAME_M1``.
        count:     Number of candles to retrieve (default: 100).

    Returns:
        list[dict] — candles in standard format.
        []         — MT5 returned no data (logged as warning).
        None       — all retries exhausted (error logged).
    """
    if mt5 is None:
        logger.error("MetaTrader5 not available — cannot fetch candles.")
        return None

    if timeframe is None:
        timeframe = mt5.TIMEFRAME_M1

    for attempt in range(1, _RETRY_COUNT + 1):
        try:
            raw = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if raw is None:
                logger.warning(
                    "copy_rates_from_pos returned None for %s (attempt %d/%d): %s",
                    symbol, attempt, _RETRY_COUNT, mt5.last_error(),
                )
            elif len(raw) == 0:
                logger.warning("MT5 returned empty candle list for %s.", symbol)
                return []
            else:
                return _candles_to_dicts(symbol, raw)
        except Exception as exc:
            logger.error(
                "Exception fetching candles for %s (attempt %d/%d): %s",
                symbol, attempt, _RETRY_COUNT, exc,
            )

        if attempt < _RETRY_COUNT:
            time.sleep(_RETRY_DELAY)

    logger.error("All %d retries failed fetching candles for %s.", _RETRY_COUNT, symbol)
    return None


def get_historical_data(
    symbol: str = settings.SYMBOL,
    timeframe=None,
    start_date: datetime = None,
    end_date: datetime = None,
):
    """Fetch OHLCV candles for *symbol* between *start_date* and *end_date*.

    Retries up to 3 times with a 2-second delay between attempts.

    Args:
        symbol:     Trading symbol (default: settings.SYMBOL).
        timeframe:  MT5 timeframe constant. Defaults to ``mt5.TIMEFRAME_M1``.
        start_date: Inclusive start datetime (UTC). Defaults to 30 days ago.
        end_date:   Inclusive end datetime (UTC). Defaults to now.

    Returns:
        list[dict] — candles in standard format.
        []         — MT5 returned no data for the range.
        None       — all retries failed; error has been logged.
    """
    if mt5 is None:
        logger.error("MetaTrader5 not available — cannot fetch historical data.")
        return None

    if timeframe is None:
        timeframe = mt5.TIMEFRAME_M1
    if end_date is None:
        end_date = datetime.utcnow()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    for attempt in range(1, _RETRY_COUNT + 1):
        try:
            raw = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
            if raw is None:
                logger.warning(
                    "copy_rates_range returned None for %s (attempt %d/%d): %s",
                    symbol, attempt, _RETRY_COUNT, mt5.last_error(),
                )
            elif len(raw) == 0:
                logger.warning(
                    "MT5 returned empty historical data for %s (%s → %s).",
                    symbol, start_date, end_date,
                )
                return []
            else:
                return _candles_to_dicts(symbol, raw)
        except Exception as exc:
            logger.error(
                "Exception fetching historical data for %s (attempt %d/%d): %s",
                symbol, attempt, _RETRY_COUNT, exc,
            )

        if attempt < _RETRY_COUNT:
            time.sleep(_RETRY_DELAY)

    logger.error(
        "All %d retries failed fetching historical data for %s.", _RETRY_COUNT, symbol
    )
    return None
