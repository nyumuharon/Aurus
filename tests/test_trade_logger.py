import os
import sqlite3
import csv
import pytest
from src.monitoring import trade_logger
from config import settings

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_journal.db"
    csv_path = tmp_path / "test_history.csv"
    
    # Save original paths
    orig_db = settings.JOURNAL_DB_PATH
    orig_csv = settings.JOURNAL_CSV_PATH
    
    # Set to temp paths
    settings.JOURNAL_DB_PATH = str(db_path)
    settings.JOURNAL_CSV_PATH = str(csv_path)
    settings.ACCOUNT_BALANCE = 10000.0
    
    trade_logger.initialize_db()
    
    yield db_path, csv_path
    
    # Restore
    settings.JOURNAL_DB_PATH = orig_db
    settings.JOURNAL_CSV_PATH = orig_csv

def test_initialize_db(temp_db):
    db_path, _ = temp_db
    assert os.path.exists(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_journal'")
        assert cursor.fetchone() is not None

def test_log_signal(temp_db):
    db_path, _ = temp_db
    trade_logger.log_signal({"final_signal": "BUY", "confidence": 0.85})
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT signal, status FROM trade_journal")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "BUY"
        assert row[1] == "PENDING_VALIDATION"

def test_log_validation(temp_db):
    db_path, _ = temp_db
    trade_logger.log_signal({"final_signal": "BUY", "confidence": 0.85})
    trade_logger.log_validation({"validated": True, "reason": "Looks good"})
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT validated, status FROM trade_journal")
        row = cursor.fetchone()
        assert row[0] == 1
        assert row[1] == "PENDING_RISK"

def test_log_risk_decision(temp_db):
    db_path, _ = temp_db
    trade_logger.log_signal({"final_signal": "BUY", "confidence": 0.85})
    trade_logger.log_validation({"validated": True, "reason": "Looks good"})
    trade_logger.log_risk_decision({"decision": "APPROVED", "lot_size": 0.1, "stop_loss": 100.0, "take_profit": 200.0, "risk_reward_ratio": 2.0})
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT risk_decision, lot_size, status FROM trade_journal")
        row = cursor.fetchone()
        assert row[0] == "APPROVED"
        assert row[1] == 0.1
        assert row[2] == "PENDING_EXECUTION"

def test_log_execution(temp_db):
    db_path, _ = temp_db
    trade_logger.log_signal({"final_signal": "BUY", "confidence": 0.85})
    trade_logger.log_validation({"validated": True, "reason": "Looks good"})
    trade_logger.log_risk_decision({"decision": "APPROVED", "lot_size": 0.1, "stop_loss": 100.0, "take_profit": 200.0, "risk_reward_ratio": 2.0})
    trade_logger.log_execution({"ticket": 12345, "entry_price": 150.0})
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticket, status FROM trade_journal")
        row = cursor.fetchone()
        assert row[0] == 12345
        assert row[1] == "OPEN"

def test_log_trade_close(temp_db):
    db_path, _ = temp_db
    trade_logger.log_signal({"final_signal": "BUY", "confidence": 0.85})
    trade_logger.log_validation({"validated": True, "reason": "Looks good"})
    trade_logger.log_risk_decision({"decision": "APPROVED", "lot_size": 0.1, "stop_loss": 100.0, "take_profit": 200.0, "risk_reward_ratio": 2.0})
    trade_logger.log_execution({"ticket": 12345, "entry_price": 150.0})
    trade_logger.log_trade_close(12345, 200.0, 50.0)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT exit_price, pnl, status FROM trade_journal")
        row = cursor.fetchone()
        assert row[0] == 200.0
        assert row[1] == 50.0
        assert row[2] == "CLOSED"

def test_get_performance_metrics_keys(temp_db):
    metrics = trade_logger.get_performance_metrics()
    required_keys = [
        "total_trades", "winning_trades", "losing_trades", "win_rate",
        "gross_profit", "gross_loss", "net_pnl", "profit_factor",
        "average_win", "average_loss", "average_rr", "max_drawdown_pct",
        "current_streak", "best_trade", "worst_trade", "trading_days"
    ]
    for key in required_keys:
        assert key in metrics

def test_get_performance_metrics_win_rate(temp_db):
    db_path, _ = temp_db
    # Add two winning and one losing trade
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trade_journal (status, pnl, timestamp, signal) VALUES ('CLOSED', 100, '2026-05-19', 'BUY')")
        cursor.execute("INSERT INTO trade_journal (status, pnl, timestamp, signal) VALUES ('CLOSED', 50, '2026-05-19', 'BUY')")
        cursor.execute("INSERT INTO trade_journal (status, pnl, timestamp, signal) VALUES ('CLOSED', -50, '2026-05-19', 'BUY')")
        conn.commit()
    
    metrics = trade_logger.get_performance_metrics()
    assert metrics["win_rate"] == round(2/3, 3)

def test_get_performance_metrics_profit_factor(temp_db):
    db_path, _ = temp_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trade_journal (status, pnl, timestamp, signal) VALUES ('CLOSED', 100, '2026-05-19', 'BUY')")
        cursor.execute("INSERT INTO trade_journal (status, pnl, timestamp, signal) VALUES ('CLOSED', -50, '2026-05-19', 'BUY')")
        conn.commit()
    
    metrics = trade_logger.get_performance_metrics()
    assert metrics["profit_factor"] == 2.0

def test_get_performance_metrics_empty(temp_db):
    metrics = trade_logger.get_performance_metrics()
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["profit_factor"] == 0.0

def test_get_recent_trades_count(temp_db):
    db_path, _ = temp_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for i in range(5):
            cursor.execute("INSERT INTO trade_journal (timestamp, signal) VALUES (?, 'BUY')", (f"2026-05-19T10:0{i}:00",))
        conn.commit()
    
    trades = trade_logger.get_recent_trades(3)
    assert len(trades) == 3

def test_get_recent_trades_order(temp_db):
    db_path, _ = temp_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for i in range(5):
            cursor.execute("INSERT INTO trade_journal (timestamp, signal) VALUES (?, 'BUY')", (f"2026-05-19T10:0{i}:00",))
        conn.commit()
    
    trades = trade_logger.get_recent_trades(3)
    assert trades[0]["timestamp"] == "2026-05-19T10:04:00"

def test_export_to_csv_creates_file(temp_db):
    db_path, csv_path = temp_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trade_journal (timestamp, signal) VALUES ('2026-05-19T10:00:00', 'BUY')")
        conn.commit()
    
    assert trade_logger.export_to_csv() is True
    assert os.path.exists(csv_path)

def test_export_to_csv_headers(temp_db):
    db_path, csv_path = temp_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trade_journal (timestamp, signal) VALUES ('2026-05-19T10:00:00', 'BUY')")
        conn.commit()
    
    trade_logger.export_to_csv()
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        assert "timestamp" in headers
        assert "signal" in headers

def test_log_functions_graceful_none(temp_db):
    # None input should return without exception
    trade_logger.log_signal(None)
    trade_logger.log_validation(None)
    trade_logger.log_risk_decision(None)
    trade_logger.log_execution(None)
    trade_logger.log_trade_close(None, None, None)
