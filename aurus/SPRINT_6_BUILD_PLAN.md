# Aurus — Sprint 6 Agent Build Plan
## Monitoring & System Integration — Staged Construction

**Version:** 1.0
**Sprint:** 6 of 6
**Senior Principal Engineer:** Claude
**Lead Engineer:** Haron
**Goal:** Build the monitoring layer — trade journal, Telegram alerts, performance dashboard — and run the full system integration test to confirm all six layers work together end-to-end. This is the final sprint. After this, Aurus is complete.

---

## Critical Rules for the Agent

- Build **one stage at a time** — do not jump ahead
- After each stage, run the tests for that stage only
- Only proceed to the next stage when every test passes
- Every function must have a docstring
- Every function must have try/except error handling
- Every file must have a module-level comment block at the top
- No hardcoded values — all constants come from `config/settings.py`
- Never use `print()` for errors — use Python `logging` module only
- **Monitoring must never stop trading** — if any monitoring component fails, log and continue
- **The 5-minute integration test is mandatory** — do not close this sprint without it
- This is the final sprint — production quality only

---

## Architecture Reminder

```
All Layers (1-5)
      |
      v
[ trade_logger.py ]     <- Stage 1
  - Log every trade to SQLite
  - Generate performance metrics
  - Export trade history to CSV
      |
      v
[ telegram_bot.py ]     <- Stage 2
  - Send trade open alerts
  - Send trade close alerts
  - Send daily summary
  - Send system status alerts
      |
      v
[ dashboard.py ]        <- Stage 3
  - Flask web dashboard
  - Live equity curve
  - Win rate and drawdown gauge
  - Recent trades table
      |
      v
[ main.py ]             <- Stage 4
  - Full system integration
  - Event loop orchestration
  - Graceful shutdown
```

---

## File Structure Being Built

```
aurus/
  src/
    monitoring/
      __init__.py
      trade_logger.py       <- Stage 1
      telegram_bot.py       <- Stage 2
      dashboard.py          <- Stage 3
  main.py                   <- Stage 4
  tests/
    test_trade_logger.py    <- Stage 1 test
    test_telegram_bot.py    <- Stage 2 test
    test_dashboard.py       <- Stage 3 test
    test_main.py            <- Stage 4 test
  data/
    journal.db
  logs/
    aurus.log
```

---

## Constants to Add to `config/settings.py`

Append the following block to the bottom of the existing `settings.py`:

```python
# -- Sprint 6 - Monitoring --------------------------------------------

# Trade journal
JOURNAL_DB_PATH = "data/journal.db"
JOURNAL_CSV_PATH = "data/trade_history.csv"

# Telegram
TELEGRAM_BOT_TOKEN = ""              # set before live trading
TELEGRAM_CHAT_ID = ""               # set before live trading
TELEGRAM_ENABLED = False             # set True when credentials added

# Dashboard
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 5000
DASHBOARD_DEBUG = False

# System
SYSTEM_LOG_FILE = "logs/aurus.log"
MAIN_LOOP_INTERVAL_SECONDS = 60     # check for new signals every 60 seconds
SYSTEM_NAME = "Aurus v1.0"
```

---

## Stage 1 - Trade Logger (`trade_logger.py`)

### What this module does

Records every trade decision, validation result, risk decision, and execution result into a unified SQLite journal. Calculates performance metrics including win rate, profit factor, average R/R, and maximum drawdown. Can export full trade history to CSV.

### File to create

`src/monitoring/trade_logger.py`

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `initialize_db()` | Create journal SQLite tables | `None` |
| `log_signal(ensemble_result)` | Log ensemble signal with all model votes | `None` |
| `log_validation(validation_result)` | Log AI validator decision | `None` |
| `log_risk_decision(risk_result)` | Log risk manager decision | `None` |
| `log_execution(order_result)` | Log order execution result | `None` |
| `log_trade_close(ticket, exit_price, pnl)` | Log trade close with final P&L | `None` |
| `get_performance_metrics()` | Calculate and return performance stats | `dict` |
| `get_recent_trades(count)` | Return last N trades from journal | `list[dict]` |
| `export_to_csv()` | Export full trade history to CSV | `True` or `False` |

### SQLite Schema

```sql
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
);

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
);
```

### Output format of `get_performance_metrics()`

```python
{
    "total_trades": 47,
    "winning_trades": 26,
    "losing_trades": 21,
    "win_rate": 0.553,
    "gross_profit": 1840.50,
    "gross_loss": -920.25,
    "net_pnl": 920.25,
    "profit_factor": 2.00,
    "average_win": 70.79,
    "average_loss": -43.82,
    "average_rr": 1.95,
    "max_drawdown_pct": 0.043,
    "current_streak": 3,
    "best_trade": 185.50,
    "worst_trade": -95.25,
    "trading_days": 12
}
```

### Error handling rules

- If SQLite write fails -> log error, do not crash — monitoring failure must never stop trading
- If metrics calculation fails -> log error, return dict with zero values
- If CSV export fails -> log error, return False
- All log functions must accept None input and handle gracefully

### Stage 1 Test (`tests/test_trade_logger.py`)

```
1.  initialize_db() creates required tables without error
2.  log_signal() writes to journal without error
3.  log_validation() writes to journal without error
4.  log_risk_decision() writes to journal without error
5.  log_execution() writes to journal without error
6.  log_trade_close() updates trade record with exit price and P&L
7.  get_performance_metrics() returns dict with all required keys
8.  get_performance_metrics() calculates win_rate correctly
9.  get_performance_metrics() calculates profit_factor correctly
10. get_performance_metrics() returns zero values on empty journal
11. get_recent_trades() returns correct number of trades
12. get_recent_trades() returns most recent trades first
13. export_to_csv() creates CSV file at correct path
14. export_to_csv() CSV contains correct column headers
15. All log functions handle None input gracefully without crashing
```

### Stage 1 Acceptance Check

```
src/monitoring/__init__.py created                    [ ]
trade_logger.py exists in src/monitoring/             [ ]
All 9 functions implemented                           [ ]
SQLite tables created correctly                       [ ]
Performance metrics calculating correctly             [ ]
All 15 tests passing                                  [ ]
Sample metrics print to terminal                      [ ]
```

**Do not proceed to Stage 2 until all are checked.**

---

## Stage 2 - Telegram Bot (`telegram_bot.py`)

**Depends on:** Stage 1 complete and accepted

### What this module does

Sends real-time alerts to a Telegram chat when trades open, close, or when the system encounters critical errors. Also sends a daily performance summary. Must work gracefully when Telegram credentials are not configured.

### File to create

`src/monitoring/telegram_bot.py`

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `is_configured()` | Check if bot token and chat ID are set | `True` or `False` |
| `send_message(text)` | Send a plain text message | `True` or `False` |
| `send_trade_open_alert(order_result)` | Alert when trade opens | `True` or `False` |
| `send_trade_close_alert(ticket, pnl, reason)` | Alert when trade closes | `True` or `False` |
| `send_daily_summary(metrics)` | Send daily performance summary | `True` or `False` |
| `send_system_alert(level, message)` | Send WARNING or CRITICAL alert | `True` or `False` |

### Message Templates

**Trade Open:**
```
AURUS TRADE OPEN
================
Symbol:      XAUUSD
Direction:   BUY
Lot size:    0.06
Entry:       2988.75
Stop loss:   2973.75
Take profit: 3018.75
R/R ratio:   2.0
Time:        2026-03-01 10:00:00 UTC
```

**Trade Close:**
```
AURUS TRADE CLOSED
==================
Symbol:  XAUUSD
Ticket:  123456789
P&L:     +$37.50
Reason:  Take profit hit
Time:    2026-03-01 14:30:00 UTC
```

**Daily Summary:**
```
AURUS DAILY SUMMARY
===================
Date:         2026-03-01
Trades today: 2
Win rate:     100.0%
Net P&L:      +$74.25
Total P&L:    +$920.25
Max drawdown: 1.2%
Status:       ACTIVE
```

### Telegram API call

```python
import requests

def send_message(text):
    if not is_configured():
        logging.info("Telegram not configured - message skipped")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.warning(f"Telegram send failed: {e}")
        return False
```

### Error handling rules

- If not configured -> log info, return False silently
- If API call fails -> log warning, return False
- If API times out -> log warning, return False
- Never block the main trading loop waiting for Telegram
- Never raise an exception

### Stage 2 Test (`tests/test_telegram_bot.py`)

```
1.  is_configured() returns False when token is empty
2.  is_configured() returns False when chat_id is empty
3.  is_configured() returns True when both are set (mock)
4.  send_message() returns False when not configured
5.  send_message() returns True on successful API call (mock)
6.  send_message() returns False on API failure (mock)
7.  send_trade_open_alert() returns False when not configured
8.  send_trade_open_alert() formats message with correct fields
9.  send_trade_close_alert() formats P&L correctly
10. send_daily_summary() formats all metric fields
11. send_system_alert() includes level in message
12. All functions return False gracefully when Telegram is down
13. No function raises an exception under any failure condition
```

### Stage 2 Acceptance Check

```
telegram_bot.py exists in src/monitoring/            [ ]
All 6 functions implemented                          [ ]
Graceful handling when not configured                [ ]
Message templates formatted correctly                [ ]
All 13 tests passing                                 [ ]
```

**Do not proceed to Stage 3 until all are checked.**

---

## Stage 3 - Dashboard (`dashboard.py`)

**Depends on:** Stage 2 complete and accepted

### What this module does

A lightweight Flask web dashboard accessible at `http://127.0.0.1:5000` while Aurus is running. Shows performance metrics, equity curve, and recent trades. Runs in a background thread — never blocks trading.

### File to create

`src/monitoring/dashboard.py`

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `start()` | Start Flask dashboard in background thread | `None` |
| `stop()` | Stop dashboard server | `None` |
| `is_running()` | Check if dashboard is active | `True` or `False` |
| `get_dashboard_data()` | Collect all data for dashboard render | `dict` |

### Flask Routes

```
GET /              -> renders main dashboard HTML page
GET /api/metrics   -> returns performance metrics as JSON
GET /api/trades    -> returns recent 20 trades as JSON
GET /api/status    -> returns system component status as JSON
```

### Dashboard Layout (single HTML file, inline CSS and JS)

```
+--------------------------------------------------+
| AURUS v1.0              [ACTIVE] [timestamp]     |
+--------------------------------------------------+
| Net P&L     Win Rate    Trades    Max Drawdown   |
| +$920.25    55.3%       47        4.3%           |
+--------------------------------------------------+
| Recent Trades                                    |
| Time     Dir   Entry    Exit     P&L    Result   |
| 10:00    BUY   2988.75  3003.75  +37.50  WIN     |
| 09:00    SELL  2995.00  2980.00  +75.00  WIN     |
+--------------------------------------------------+
```

Use plain HTML table and inline CSS. No external JS libraries required. Auto-refresh every 30 seconds using a meta refresh tag.

### Error handling rules

- If Flask fails to start -> log error, do not crash trading system
- If port is already in use -> log error, try DASHBOARD_PORT + 1
- If data fetch fails -> render dashboard with empty/zero values
- Dashboard failure must never stop trading

### Stage 3 Test (`tests/test_dashboard.py`)

```
1.  start() starts dashboard thread without error
2.  is_running() returns True after start()
3.  stop() stops dashboard cleanly
4.  is_running() returns False after stop()
5.  get_dashboard_data() returns dict with metrics and trades keys
6.  /api/metrics endpoint returns 200 with JSON (Flask test client)
7.  /api/trades endpoint returns 200 with JSON
8.  /api/status endpoint returns 200 with JSON
9.  / endpoint returns 200 HTML response
10. Dashboard handles empty trade journal gracefully
```

### Stage 3 Acceptance Check

```
dashboard.py exists in src/monitoring/               [ ]
All 4 functions implemented                          [ ]
Flask routes returning correct responses             [ ]
Dashboard accessible at localhost:5000               [ ]
All 10 tests passing                                 [ ]
Dashboard renders in browser confirmed               [ ]
```

**Do not proceed to Stage 4 until all are checked.**

---

## Stage 4 - Main System (`main.py`)

**Depends on:** All previous stages complete and accepted

### What this module does

The entry point for the entire Aurus system. Initializes all six layers in the correct order, runs the main event loop, handles graceful shutdown on Ctrl+C, and coordinates all components.

### File to create

`main.py` (project root)

### System Startup Sequence

```
1.  Initialize logging
2.  Initialize trade journal DB
3.  Initialize risk manager DB
4.  Initialize execution DB
5.  Start Data Manager
6.  Check Ollama connection
7.  Connect to MT5
8.  Start trade monitor
9.  Start dashboard
10. Send Telegram startup alert
11. Enter main signal loop
```

### Main Signal Loop

```python
while running:
    try:
        # 1 - Get market snapshot
        snapshot = data_manager.get_market_snapshot()
        if snapshot["status"] == "ERROR":
            time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
            continue

        # 2 - Get ensemble signal
        signal = ensemble.get_ensemble_signal()
        if signal["final_signal"] == "NO_TRADE":
            time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
            continue

        # 3 - Validate with AI
        validation = ai_validator.validate(signal, snapshot)
        if not validation["validated"]:
            time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
            continue

        # 4 - Risk check
        risk = risk_manager.evaluate(validation, snapshot)
        if risk["decision"] == "BLOCKED":
            time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
            continue

        # 5 - Execute
        order = mt5_connector.send_order(risk)
        if order:
            trade_logger.log_execution(order)
            telegram_bot.send_trade_open_alert(order)

    except Exception as e:
        logging.critical(f"Main loop error: {e}")
        telegram_bot.send_system_alert("CRITICAL", str(e))

    time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
```

### Graceful Shutdown

```python
import signal as sys_signal
import sys

def shutdown(signum, frame):
    logging.info("Shutdown signal received")
    telegram_bot.send_system_alert("WARNING", "Aurus shutting down")
    trade_manager.stop()
    dashboard.stop()
    data_manager.stop()
    mt5_connector.disconnect()
    logging.info("Aurus shutdown complete")
    sys.exit(0)

sys_signal.signal(sys_signal.SIGINT, shutdown)
sys_signal.signal(sys_signal.SIGTERM, shutdown)
```

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `initialize_system()` | Run full startup sequence | `True` or `False` |
| `run_signal_cycle(snapshot)` | Execute one full signal detection cycle | `dict` or `None` |
| `shutdown(signum, frame)` | Handle graceful shutdown | `None` |
| `main()` | Entry point — initialize then loop | `None` |

### Stage 4 Test (`tests/test_main.py`)

```
1.  initialize_system() returns True when all components start
2.  initialize_system() returns False when critical component fails
3.  run_signal_cycle() returns None when snapshot status is ERROR
4.  run_signal_cycle() returns None when signal is NO_TRADE
5.  run_signal_cycle() returns None when validation fails
6.  run_signal_cycle() returns None when risk decision is BLOCKED
7.  run_signal_cycle() returns order dict when all layers approve
8.  Main loop continues after single cycle exception
9.  shutdown() stops all components cleanly
10. shutdown() sends Telegram alert before stopping
```

### Stage 4 Acceptance Check

```
main.py exists in project root                        [ ]
All 4 functions implemented                           [ ]
Startup sequence runs in correct order                [ ]
Main loop handles all failure cases without crashing  [ ]
Graceful shutdown on Ctrl+C confirmed                 [ ]
All 10 tests passing                                  [ ]
System runs for 5 minutes without crashing            [ ]
All code committed to GitHub                          [ ]
```

---

## Sprint 6 Final Acceptance

Sprint 6 is closed only when every stage acceptance check is complete:

```
Stage 1 - Trade Logger          [ ]
Stage 2 - Telegram Bot          [ ]
Stage 3 - Dashboard             [ ]
Stage 4 - Main System           [ ]
All 48 tests passing            [ ]
5-minute integration run        [ ]
All code on GitHub              [ ]
```

### 5-Minute Integration Test

```fish
python main.py
```

Watch for 5 minutes. The system must:
- Start all components without error
- Print signal cycle results every 60 seconds
- Not crash on any data feed failure
- Dashboard accessible at http://127.0.0.1:5000
- Shut down cleanly on Ctrl+C

---

## Full System Test After Sprint 6

Run the complete test suite one final time:

```fish
python -m pytest tests/ -v --ignore=.venv --tb=short 2>&1 | tail -20
```

Target: **367+ tests passing across all 6 sprints.**

---

## Aurus Completion Checklist

```
All 6 sprints completed                              [ ]
367+ total tests passing                             [ ]
main.py runs 5 minutes without crash                 [ ]
Dashboard renders correctly                          [ ]
All code on GitHub                                   [ ]
docs/ folder has all 6 sprint build plans            [ ]
README.md reflects final system                      [ ]
```

---

## After Aurus — The Path to a Funded Account

```
Month 1: Run on demo for 30 days
         Track all metrics in journal
         Target: profit factor > 1.5, drawdown < 5%

Month 2: Review and optimize
         Retrain models on recent data
         Adjust ensemble weights if needed

Month 3: Select prop firm challenge
         FTMO, MyFundedFx, or The5%ers
         Start with smallest challenge size ($10K)

Month 4: Run Aurus on challenge account
         Monitor daily via dashboard
         Do not interfere with the system

Month 5: Pass evaluation -> funded account
```

---

## Important Reminders for the Agent

1. **Monitoring must never stop trading** — if logger, Telegram, or dashboard fails, log and continue
2. **main.py is the conductor** — it calls functions from the six layers in order, contains no business logic itself
3. **The 5-minute test is mandatory** — do not close Sprint 6 without running main.py for 5 minutes
4. **Clean shutdown matters** — Ctrl+C must close all threads and connections gracefully
5. **This is the last sprint** — production quality only. No shortcuts.

---

*Aurus Sprint 6 - Monitoring and Integration. The final piece. Build it right.*
