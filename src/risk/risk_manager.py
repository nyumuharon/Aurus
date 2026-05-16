"""
Risk Manager Module

Enforces all capital protection rules before any trade is approved.
"""

import sqlite3
import logging
import os
import traceback
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)

def initialize_db():
    """Create SQLite tables for risk tracking."""
    try:
        os.makedirs(os.path.dirname(settings.RISK_DB_PATH), exist_ok=True)
        with sqlite3.connect(settings.RISK_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id      TEXT NOT NULL,
                    signal        TEXT NOT NULL,
                    lot_size      REAL NOT NULL,
                    entry_price   REAL NOT NULL,
                    stop_loss     REAL NOT NULL,
                    take_profit   REAL NOT NULL,
                    open_time     TEXT NOT NULL,
                    close_time    TEXT,
                    exit_price    REAL,
                    pnl           REAL,
                    status        TEXT DEFAULT 'OPEN'
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_summary (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    date          TEXT NOT NULL UNIQUE,
                    trade_count   INTEGER DEFAULT 0,
                    daily_pnl     REAL DEFAULT 0.0,
                    peak_balance  REAL NOT NULL,
                    close_balance REAL
                );
            ''')
            
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT id FROM daily_summary WHERE date = ?", (today,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO daily_summary (date, peak_balance)
                    VALUES (?, ?)
                """, (today, settings.ACCOUNT_BALANCE))
            conn.commit()
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")

def get_daily_stats():
    """Get today's trade count and P&L from DB."""
    try:
        with sqlite3.connect(settings.RISK_DB_PATH) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT trade_count, daily_pnl FROM daily_summary WHERE date = ?", (today,))
            row = cursor.fetchone()
            if row:
                return {"trade_count": row[0], "daily_pnl": row[1]}
            else:
                return {"trade_count": 0, "daily_pnl": 0.0}
    except Exception as e:
        logger.error(f"Error getting daily stats: {e}")
        return {"trade_count": 0, "daily_pnl": 0.0}

def get_total_drawdown():
    """Calculate total drawdown from account peak."""
    try:
        with sqlite3.connect(settings.RISK_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(peak_balance) FROM daily_summary")
            row = cursor.fetchone()
            peak = row[0] if row and row[0] else settings.ACCOUNT_BALANCE
            
            cursor.execute("SELECT close_balance FROM daily_summary ORDER BY date DESC LIMIT 1")
            row2 = cursor.fetchone()
            current = row2[0] if row2 and row2[0] is not None else settings.ACCOUNT_BALANCE
            
            if peak <= 0:
                return 0.0
                
            dd = (peak - current) / peak
            return max(0.0, dd)
    except Exception as e:
        logger.error(f"Error getting total drawdown: {e}")
        return 0.0

def check_daily_loss(daily_pnl):
    """Check if daily loss limit is breached."""
    try:
        if daily_pnl >= 0:
            return True
        loss_pct = abs(daily_pnl) / settings.ACCOUNT_BALANCE
        return loss_pct < settings.MAX_DAILY_LOSS_PCT
    except Exception as e:
        logger.error(f"Error checking daily loss: {e}")
        return False

def check_total_drawdown(drawdown):
    """Check if total drawdown limit is breached."""
    try:
        return drawdown < settings.MAX_TOTAL_DRAWDOWN_PCT
    except Exception as e:
        logger.error(f"Error checking total drawdown: {e}")
        return False

def check_trade_count(trade_count):
    """Check if max trades per day is reached."""
    try:
        return trade_count < settings.MAX_TRADES_PER_DAY
    except Exception as e:
        logger.error(f"Error checking trade count: {e}")
        return False

def check_high_impact_window(calendar_data):
    """Check if high impact event is imminent."""
    try:
        if calendar_data and calendar_data.get("high_impact_window"):
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking high impact window: {e}")
        return False

def get_default_block(reason):
    """Return standard BLOCKED result."""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signal": "UNKNOWN",
        "decision": "BLOCKED",
        "reason": reason,
        "lot_size": 0.0,
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "risk_reward": 0.0,
        "daily_trade_count": 0,
        "daily_pnl": 0.0,
        "total_drawdown_pct": 0.0,
        "account_balance": 0.0,
        "passed_to_execution": False
    }

def record_trade_open(trade_id, signal, lot_size, entry_price, sl, tp):
    """Log trade open to SQLite."""
    try:
        with sqlite3.connect(settings.RISK_DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO trades (trade_id, signal, lot_size, entry_price, stop_loss, take_profit, open_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (trade_id, signal, lot_size, entry_price, sl, tp, now))
            
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                UPDATE daily_summary 
                SET trade_count = trade_count + 1
                WHERE date = ?
            """, (today,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error recording trade open: {e}")

def record_trade_close(trade_id, exit_price, pnl):
    """Log trade close and update daily P&L."""
    try:
        with sqlite3.connect(settings.RISK_DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE trades 
                SET close_time = ?, exit_price = ?, pnl = ?, status = 'CLOSED'
                WHERE trade_id = ?
            """, (now, exit_price, pnl, trade_id))
            
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                UPDATE daily_summary 
                SET daily_pnl = daily_pnl + ?
                WHERE date = ?
            """, (pnl, today))
            
            cursor.execute("SELECT daily_pnl, peak_balance FROM daily_summary WHERE date = ?", (today,))
            row = cursor.fetchone()
            if row:
                daily_pnl = row[0]
                cursor.execute("""
                    UPDATE daily_summary 
                    SET close_balance = ? + ?
                    WHERE date = ?
                """, (settings.ACCOUNT_BALANCE, daily_pnl, today))
            conn.commit()
    except Exception as e:
        logger.error(f"Error recording trade close: {e}")

def evaluate(validation_result, market_snapshot):
    """Run all checks and return risk decision."""
    try:
        if not validation_result or not validation_result.get("validated"):
            return get_default_block("Trade not validated by AI")
            
        if not market_snapshot or "price" not in market_snapshot:
            logger.error("Missing price data")
            return get_default_block("Missing price data")
            
        price_data = market_snapshot["price"]
        if "latest_candle" not in price_data or "close" not in price_data["latest_candle"]:
            logger.error("Missing price data")
            return get_default_block("Missing price data")
            
        calendar_data = market_snapshot.get("calendar", {})
        if not check_high_impact_window(calendar_data):
            return get_default_block("High impact event imminent")
            
        initialize_db()
            
        dd = get_total_drawdown()
        if not check_total_drawdown(dd):
            return get_default_block("Total drawdown limit reached - system halted")
            
        stats = get_daily_stats()
        if not check_daily_loss(stats["daily_pnl"]):
            return get_default_block("Daily loss limit reached")
            
        if not check_trade_count(stats["trade_count"]):
            return get_default_block("Maximum trades per day reached")
            
        # Real position_sizer call
        from src.risk.position_sizer import get_position_parameters
        signal = validation_result.get("signal", "UNKNOWN")
        entry_price = price_data["latest_candle"]["close"]
        candles = price_data.get("candles_1m", [])
        
        pos_params = get_position_parameters(signal, entry_price, candles, settings.ACCOUNT_BALANCE)
        if not pos_params or pos_params.get("lot_size", 0) <= 0:
            return get_default_block("Position size calculation failed")
            
        if pos_params.get("risk_reward", 0) < settings.MIN_RISK_REWARD_RATIO:
            return get_default_block("Risk/reward ratio below minimum")
        
        return {
            "timestamp": validation_result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "signal": validation_result.get("signal", "UNKNOWN"),
            "decision": "APPROVED",
            "reason": "All risk checks passed",
            "lot_size": pos_params["lot_size"],
            "entry_price": pos_params["entry_price"],
            "stop_loss": pos_params["stop_loss"],
            "take_profit": pos_params["take_profit"],
            "risk_reward": pos_params["risk_reward"],
            "daily_trade_count": stats["trade_count"],
            "daily_pnl": stats["daily_pnl"],
            "total_drawdown_pct": dd,
            "account_balance": settings.ACCOUNT_BALANCE,
            "passed_to_execution": True
        }
            
    except sqlite3.Error as e:
        logger.critical(f"Database error: {e}", exc_info=True)
        return get_default_block("Database error")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        return get_default_block("Unexpected error")
