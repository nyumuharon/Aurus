"""
Trade logger module for Aurus.
Handles logging trade decisions, validations, risk decisions, executions,
and calculates performance metrics.
"""
import sqlite3
import csv
import logging
import os
from datetime import datetime
from config import settings

def initialize_db():
    """Create journal SQLite tables if they do not exist."""
    try:
        os.makedirs(os.path.dirname(settings.JOURNAL_DB_PATH), exist_ok=True)
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_journal (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket            INTEGER,
                    timestamp         TEXT NOT NULL,
                    signal            TEXT NOT NULL,
                    ensemble_score    REAL,
                    validated         INTEGER,
                    validation_reason TEXT,
                    risk_decision     TEXT,
                    lot_size          REAL,
                    entry_price       REAL,
                    stop_loss         REAL,
                    take_profit       REAL,
                    risk_reward       REAL,
                    exit_price        REAL,
                    pnl               REAL,
                    status            TEXT DEFAULT 'OPEN',
                    notes             TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_performance (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    date            TEXT NOT NULL UNIQUE,
                    total_trades    INTEGER DEFAULT 0,
                    winning_trades  INTEGER DEFAULT 0,
                    losing_trades   INTEGER DEFAULT 0,
                    gross_profit    REAL DEFAULT 0.0,
                    gross_loss      REAL DEFAULT 0.0,
                    net_pnl         REAL DEFAULT 0.0,
                    win_rate        REAL DEFAULT 0.0,
                    profit_factor   REAL DEFAULT 0.0,
                    max_drawdown    REAL DEFAULT 0.0
                )
            ''')
            conn.commit()
    except Exception as e:
        logging.error(f"Error initializing DB: {e}")

def log_signal(ensemble_result):
    """Log ensemble signal with all model votes."""
    if ensemble_result is None:
        return
    try:
        timestamp = datetime.utcnow().isoformat()
        signal = ensemble_result.get("final_signal", "NO_TRADE")
        score = ensemble_result.get("confidence", 0.0)
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO trade_journal (timestamp, signal, ensemble_score, status) VALUES (?, ?, ?, 'PENDING_VALIDATION')",
                (timestamp, signal, score)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error logging signal: {e}")

def log_validation(validation_result):
    """Log AI validator decision."""
    if validation_result is None:
        return
    try:
        validated = 1 if validation_result.get("validated") else 0
        reason = validation_result.get("reason", "")
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trade_journal 
                SET validated = ?, validation_reason = ?, status = 'PENDING_RISK' 
                WHERE id = (SELECT MAX(id) FROM trade_journal WHERE status = 'PENDING_VALIDATION')
                """,
                (validated, reason)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error logging validation: {e}")

def log_risk_decision(risk_result):
    """Log risk manager decision."""
    if risk_result is None:
        return
    try:
        decision = risk_result.get("decision", "BLOCKED")
        lot_size = risk_result.get("lot_size", 0.0)
        stop_loss = risk_result.get("stop_loss", 0.0)
        take_profit = risk_result.get("take_profit", 0.0)
        risk_reward = risk_result.get("risk_reward_ratio", 0.0)
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trade_journal 
                SET risk_decision = ?, lot_size = ?, stop_loss = ?, take_profit = ?, risk_reward = ?, status = 'PENDING_EXECUTION' 
                WHERE id = (SELECT MAX(id) FROM trade_journal WHERE status = 'PENDING_RISK')
                """,
                (decision, lot_size, stop_loss, take_profit, risk_reward)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error logging risk decision: {e}")

def log_execution(order_result):
    """Log order execution result."""
    if order_result is None:
        return
    try:
        ticket = order_result.get("ticket")
        entry_price = order_result.get("entry_price", 0.0)
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trade_journal 
                SET ticket = ?, entry_price = ?, status = 'OPEN' 
                WHERE id = (SELECT MAX(id) FROM trade_journal WHERE status = 'PENDING_EXECUTION')
                """,
                (ticket, entry_price)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error logging execution: {e}")

def log_trade_close(ticket, exit_price, pnl):
    """Log trade close with final P&L."""
    if ticket is None:
        return
    try:
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trade_journal 
                SET exit_price = ?, pnl = ?, status = 'CLOSED' 
                WHERE ticket = ?
                """,
                (exit_price, pnl, ticket)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error logging trade close: {e}")

def get_performance_metrics():
    """Calculate and return performance stats."""
    default_metrics = {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_pnl": 0.0,
        "profit_factor": 0.0,
        "average_win": 0.0,
        "average_loss": 0.0,
        "average_rr": 0.0,
        "max_drawdown_pct": 0.0,
        "current_streak": 0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "trading_days": 0
    }
    
    try:
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT pnl, risk_reward FROM trade_journal WHERE status = 'CLOSED'")
            rows = cursor.fetchall()
            
            if not rows:
                return default_metrics
                
            total_trades = len(rows)
            winning_trades = sum(1 for row in rows if row[0] is not None and row[0] > 0)
            losing_trades = sum(1 for row in rows if row[0] is not None and row[0] <= 0)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            
            gross_profit = sum(row[0] for row in rows if row[0] is not None and row[0] > 0)
            gross_loss = sum(row[0] for row in rows if row[0] is not None and row[0] <= 0)
            net_pnl = gross_profit + gross_loss
            profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else (float('inf') if gross_profit > 0 else 0.0)
            
            average_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
            average_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
            
            valid_rr = [row[1] for row in rows if row[1] is not None and row[1] > 0]
            average_rr = sum(valid_rr) / len(valid_rr) if valid_rr else 0.0
            
            best_trade = max((row[0] for row in rows if row[0] is not None), default=0.0)
            worst_trade = min((row[0] for row in rows if row[0] is not None), default=0.0)
            
            equity = 0
            peak = 0
            max_drawdown = 0
            for row in rows:
                if row[0] is None: continue
                equity += row[0]
                if equity > peak:
                    peak = equity
                drawdown = peak - equity
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            max_drawdown_pct = max_drawdown / settings.ACCOUNT_BALANCE if getattr(settings, 'ACCOUNT_BALANCE', 0) > 0 else 0.0

            cursor.execute("SELECT COUNT(DISTINCT date(timestamp)) FROM trade_journal WHERE status = 'CLOSED'")
            trading_days_row = cursor.fetchone()
            trading_days = trading_days_row[0] if trading_days_row else 0
            
            current_streak = 0
            for row in reversed(rows):
                if row[0] is not None and row[0] > 0:
                    current_streak += 1
                else:
                    break
            
            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 3),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "net_pnl": round(net_pnl, 2),
                "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else float('inf'),
                "average_win": round(average_win, 2),
                "average_loss": round(average_loss, 2),
                "average_rr": round(average_rr, 2),
                "max_drawdown_pct": round(max_drawdown_pct, 3),
                "current_streak": current_streak,
                "best_trade": round(best_trade, 2),
                "worst_trade": round(worst_trade, 2),
                "trading_days": trading_days
            }
    except Exception as e:
        logging.error(f"Error calculating metrics: {e}")
        return default_metrics

def get_recent_trades(count):
    """Return last N trades from journal."""
    try:
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trade_journal ORDER BY id DESC LIMIT ?", (count,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error getting recent trades: {e}")
        return []

def export_to_csv():
    """Export full trade history to CSV."""
    try:
        os.makedirs(os.path.dirname(settings.JOURNAL_CSV_PATH), exist_ok=True)
        with sqlite3.connect(settings.JOURNAL_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trade_journal")
            rows = cursor.fetchall()
            
            if not rows:
                return True
                
            columns = [description[0] for description in cursor.description]
            with open(settings.JOURNAL_CSV_PATH, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
            return True
    except Exception as e:
        logging.error(f"Error exporting CSV: {e}")
        return False
