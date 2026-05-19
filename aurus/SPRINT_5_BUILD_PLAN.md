# Aurus — Sprint 5 Agent Build Plan
## Execution Engine — Staged Construction

**Version:** 1.0
**Sprint:** 5 of 6
**Senior Principal Engineer:** Claude
**Lead Engineer:** Haron
**Goal:** Build the Execution Engine that connects to MetaTrader 5, sends approved orders with pre-calculated SL and TP, monitors open positions, and handles partial closes and trailing stops.

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
- **ALL orders must have a stop loss — never send an order without SL**
- **Never send a live order during testing — use MT5 demo account only**
- **Every order sent must be logged before and after execution**
- If MT5 is unavailable, fail gracefully — never crash the system

---

## Architecture Reminder

```
Risk Decision (Layer 4)
          |
          v
[ mt5_connector.py ]    <- Stage 1
  - Connect to MT5
  - Send market orders
  - Set SL and TP
  - Handle order errors
          |
          v
[ trade_manager.py ]    <- Stage 2
  - Monitor open positions
  - Trailing stop updates
  - Partial close at 1:1 R/R
  - Position state tracking
          |
          v
Layer 6 - Monitoring (Sprint 6)
```

---

## File Structure Being Built

```
aurus/
  src/
    execution/
      __init__.py
      mt5_connector.py      <- Stage 1
      trade_manager.py      <- Stage 2
  tests/
    test_mt5_connector.py   <- Stage 1 test
    test_trade_manager.py   <- Stage 2 test
  data/
    execution.db            <- SQLite for order tracking
```

---

## Constants to Add to `config/settings.py`

Append the following block to the bottom of the existing `settings.py`:

```python
# -- Sprint 5 - Execution Engine --------------------------------------

# MT5 connection
MT5_LOGIN = 0                        # replace with demo account number
MT5_PASSWORD = ""                    # replace with demo account password
MT5_SERVER = ""                      # replace with broker server name
MT5_TIMEOUT_MS = 10000               # connection timeout in milliseconds

# Order settings
ORDER_SYMBOL = "XAUUSD"
ORDER_MAGIC = 202601                 # unique magic number for Aurus orders
ORDER_COMMENT = "Aurus_v1"          # order comment shown in MT5
ORDER_SLIPPAGE = 10                  # maximum slippage in points
ORDER_MAX_RETRIES = 3                # retry failed orders this many times
ORDER_RETRY_DELAY_SECONDS = 2        # delay between retries

# Position management
TRAILING_STOP_ATR_MULTIPLIER = 1.0   # trail at 1x ATR behind price
PARTIAL_CLOSE_PCT = 0.50             # close 50% of position at 1:1 R/R
PARTIAL_CLOSE_RR = 1.0               # trigger partial close at this R/R

# Execution database
EXECUTION_DB_PATH = "data/execution.db"
EXECUTION_LOG_FILE = "logs/execution.log"

# Position monitor interval
POSITION_CHECK_INTERVAL_SECONDS = 5
```

---

## Stage 1 - MT5 Connector (`mt5_connector.py`)

**Build this first. Trade manager depends on it.**

### What this module does

Manages the connection to MetaTrader 5 and handles all order operations. Sends market orders with mandatory SL and TP, retrieves open positions, modifies orders, and closes positions. All operations are logged before and after execution.

### File to create

`src/execution/mt5_connector.py`

### Important Note on MT5 on Linux

MetaTrader 5 does not have a native Linux binary. On Linux, the MetaTrader5 Python package connects to an MT5 instance running under Wine. The connector must handle the case where MT5 is unavailable gracefully.

Use this import pattern:

```python
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    # Log warning -- MT5 not available, running in simulation mode
```

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `connect()` | Connect to MT5 with credentials from settings | `True` or `False` |
| `disconnect()` | Cleanly shut down MT5 connection | `None` |
| `is_connected()` | Check if MT5 connection is alive | `True` or `False` |
| `get_account_info()` | Get current account balance and equity | `dict` or `None` |
| `send_order(risk_decision)` | Send a market order with SL and TP | `dict` or `None` |
| `get_open_positions()` | Get all open positions for Aurus orders | `list[dict]` or `None` |
| `modify_position(ticket, sl, tp)` | Modify SL and TP of an open position | `True` or `False` |
| `close_position(ticket, lot_size)` | Close a position fully or partially | `dict` or `None` |
| `get_symbol_info(symbol)` | Get symbol tick size and pip value | `dict` or `None` |

### Input format of `send_order()` (from risk_decision)

```python
{
    "signal": "BUY",
    "lot_size": 0.06,
    "entry_price": 2988.75,
    "stop_loss": 2973.75,
    "take_profit": 3018.75,
    "risk_reward": 2.0
}
```

### Output format of `send_order()`

```python
{
    "ticket": 123456789,
    "symbol": "XAUUSD",
    "signal": "BUY",
    "order_type": "ORDER_TYPE_BUY",
    "lot_size": 0.06,
    "entry_price": 2988.75,
    "stop_loss": 2973.75,
    "take_profit": 3018.75,
    "timestamp": "2026-03-01 10:00:00",
    "status": "FILLED",
    "comment": "Aurus_v1"
}
```

### Output format of `get_open_positions()`

```python
[
    {
        "ticket": 123456789,
        "symbol": "XAUUSD",
        "signal": "BUY",
        "lot_size": 0.06,
        "entry_price": 2988.75,
        "current_price": 2995.00,
        "stop_loss": 2973.75,
        "take_profit": 3018.75,
        "profit": 37.50,
        "open_time": "2026-03-01 10:00:00"
    }
]
```

### Order sending logic

```python
def send_order(risk_decision):
    # Step 1: Validate all required fields exist
    # Step 2: Abort immediately if SL is missing or zero
    # Step 3: Log the intended order before sending
    # Step 4: Build MT5 order request dict
    # Step 5: Send with mt5.order_send()
    # Step 6: Check result.retcode == mt5.TRADE_RETCODE_DONE
    # Step 7: If failed, retry up to ORDER_MAX_RETRIES times
    # Step 8: Log the result (success or failure)
    # Step 9: Return order result dict or None on failure

    # MT5 order type mapping
    # BUY  -> mt5.ORDER_TYPE_BUY
    # SELL -> mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": ORDER_SYMBOL,
        "volume": lot_size,
        "type": order_type,
        "price": mt5.symbol_info_tick(ORDER_SYMBOL).ask,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": ORDER_SLIPPAGE,
        "magic": ORDER_MAGIC,
        "comment": ORDER_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
```

### SQLite Schema

Create this table in `data/execution.db`:

```sql
CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket        INTEGER,
    symbol        TEXT NOT NULL,
    signal        TEXT NOT NULL,
    lot_size      REAL NOT NULL,
    entry_price   REAL NOT NULL,
    stop_loss     REAL NOT NULL,
    take_profit   REAL NOT NULL,
    open_time     TEXT NOT NULL,
    close_time    TEXT,
    exit_price    REAL,
    profit        REAL,
    status        TEXT DEFAULT 'OPEN',
    comment       TEXT
);
```

### Error handling rules

- If MT5 not available (Linux/no Wine) -> log warning, run in simulation mode
- If connection fails -> log error, return `False`, do not crash
- If order rejected by broker -> log error with retcode, retry up to max retries
- If order times out -> log error, return `None`
- Never send an order without SL set -- validate before sending
- If SL is missing or zero -> log critical, abort order, return `None`

### Simulation Mode

When MT5 is not available, all functions must return realistic mock data:

```python
# In simulation mode:
# connect()             -> returns True
# is_connected()        -> returns True
# get_account_info()    -> returns mock dict with ACCOUNT_BALANCE
# send_order()          -> returns mock order dict with fake ticket
# get_open_positions()  -> returns empty list
# modify_position()     -> returns True
# close_position()      -> returns mock close dict
# get_symbol_info()     -> returns mock symbol dict
```

### Stage 1 Test (`tests/test_mt5_connector.py`)

All tests must use mocks -- never require a live MT5 connection:

```
1.  connect() returns True in simulation mode
2.  disconnect() runs without error
3.  is_connected() returns correct boolean
4.  get_account_info() returns dict with balance and equity keys
5.  send_order() returns dict with all required keys for BUY signal
6.  send_order() returns dict with all required keys for SELL signal
7.  send_order() returns None when SL is missing from risk_decision
8.  send_order() returns None when SL is zero
9.  send_order() logs order details before sending
10. send_order() logs result after sending
11. get_open_positions() returns a list
12. modify_position() returns True on success (mock)
13. modify_position() returns False on failure (mock)
14. close_position() returns dict on success (mock)
15. close_position() returns None on failure (mock)
16. get_symbol_info() returns dict with tick_size and pip_value keys
17. System runs in simulation mode when MT5 is unavailable
18. All functions return safe values in simulation mode
```

### Stage 1 Acceptance Check

```
src/execution/__init__.py created                     [ ]
mt5_connector.py exists in src/execution/             [ ]
All 9 functions implemented                           [ ]
Simulation mode working when MT5 unavailable          [ ]
SL validation blocking orders without SL             [ ]
SQLite orders table created                           [ ]
All 18 tests passing                                  [ ]
Sample send_order() result prints to terminal         [ ]
```

**Do not proceed to Stage 2 until all are checked.**

---

## Stage 2 - Trade Manager (`trade_manager.py`)

**Depends on:** Stage 1 complete and accepted

### What this module does

Monitors all open Aurus positions every 5 seconds. Manages trailing stops, executes partial closes at 1:1 R/R, detects when positions are closed by SL or TP, and updates the risk manager database with final P&L. Runs in a background thread so it never blocks the main signal loop.

### File to create

`src/execution/trade_manager.py`

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `start()` | Start background position monitor thread | `None` |
| `stop()` | Stop background monitor thread cleanly | `None` |
| `is_running()` | Check if monitor thread is active | `True` or `False` |
| `monitor_positions()` | Main loop -- checks all positions every 5 seconds | `None` |
| `check_partial_close(position)` | Check if position qualifies for partial close | `True` or `False` |
| `execute_partial_close(position)` | Close 50% of position at 1:1 R/R | `True` or `False` |
| `update_trailing_stop(position)` | Move SL in correct direction as price moves | `True` or `False` |
| `detect_closed_positions()` | Find positions closed by SL or TP since last check | `list[dict]` |
| `handle_closed_position(position)` | Update risk DB with final P&L | `None` |
| `get_position_status()` | Return summary of all monitored positions | `dict` |

### Partial Close Logic

```
Trigger: current profit >= risk distance (1:1 R/R)

Example:
  Entry:      2988.75
  SL:         2973.75   (risk = 15 pips)
  TP:         3018.75   (reward = 30 pips)
  Partial at: 3003.75   (entry + 15 pips = 1:1)
  Action:     close 50% of lot size
  After:      move SL to breakeven (entry price)

Track in database whether partial close has been executed.
Only execute partial close ONCE per position.
```

### Trailing Stop Logic

```
After partial close is executed:
  Trail SL at: current_price - (ATR * TRAILING_STOP_ATR_MULTIPLIER)

For BUY positions:
  New SL = max(current_sl, current_price - trail_distance)
  Rule: SL only moves UP, never DOWN

For SELL positions:
  New SL = min(current_sl, current_price + trail_distance)
  Rule: SL only moves DOWN, never UP

Update only if new SL is better than current SL by at least 1 pip.
Update frequency: every position check cycle (5 seconds).
```

### Position State Machine

```
OPEN
  |
  +-- price reaches 1:1 R/R ---------> PARTIAL_CLOSED
  |                                           |
  |                               trailing stop activated
  |                                           |
  |                                       TRAILING
  |                                           |
  |                                    SL or TP hit
  |                                           |
  +-- SL hit directly ----------------> CLOSED
  |
  +-- TP hit directly ----------------> CLOSED
```

### Background Thread Pattern

```python
import threading
import time

_monitor_thread = None
_running = False

def start():
    global _monitor_thread, _running
    _running = True
    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        daemon=True,
        name="AurusTradeMonitor"
    )
    _monitor_thread.start()
    logging.info("Trade monitor started")

def _monitor_loop():
    while _running:
        try:
            monitor_positions()
        except Exception as e:
            logging.error(f"Monitor loop error: {e}")
        time.sleep(POSITION_CHECK_INTERVAL_SECONDS)

def stop():
    global _running
    _running = False
    logging.info("Trade monitor stopped")
```

### Output format of `get_position_status()`

```python
{
    "timestamp": "2026-03-01 10:05:00",
    "open_count": 1,
    "positions": [
        {
            "ticket": 123456789,
            "symbol": "XAUUSD",
            "signal": "BUY",
            "lot_size": 0.06,
            "entry_price": 2988.75,
            "current_price": 2995.00,
            "stop_loss": 2988.75,
            "take_profit": 3018.75,
            "profit": 37.50,
            "state": "TRAILING",
            "partial_closed": True
        }
    ],
    "total_profit": 37.50
}
```

### Error handling rules

- If MT5 connection drops during monitor loop -> log error, attempt reconnect, continue loop
- If partial close fails -> log error, do not retry, continue monitoring
- If trailing stop update fails -> log warning, continue monitoring
- Never stop the monitor thread due to a single position error
- If all positions fail to load -> log critical, pause 30 seconds, retry

### Stage 2 Test (`tests/test_trade_manager.py`)

All tests must use mocks -- never require live MT5:

```
1.  start() starts background thread without error
2.  is_running() returns True after start()
3.  stop() stops thread cleanly
4.  is_running() returns False after stop()
5.  check_partial_close() returns True when profit >= 1:1 R/R distance
6.  check_partial_close() returns False when profit < 1:1 R/R distance
7.  execute_partial_close() calls close_position with 50% of lot size
8.  execute_partial_close() moves SL to breakeven after partial close
9.  update_trailing_stop() moves SL up for profitable BUY position
10. update_trailing_stop() never moves SL down for BUY position
11. update_trailing_stop() moves SL down for profitable SELL position
12. update_trailing_stop() never moves SL up for SELL position
13. detect_closed_positions() returns empty list when no positions closed
14. detect_closed_positions() returns closed position when SL is hit (mock)
15. handle_closed_position() updates risk DB with final P&L
16. get_position_status() returns dict with required keys
17. Monitor loop continues after single position error
18. Monitor loop handles MT5 disconnect gracefully
```

### Stage 2 Acceptance Check

```
trade_manager.py exists in src/execution/            [ ]
All 10 functions implemented                         [ ]
Background thread starts and stops cleanly           [ ]
Partial close triggers at correct price level        [ ]
Trailing stop only moves in correct direction        [ ]
Position state machine implemented                   [ ]
Risk DB updated on position close                    [ ]
All 18 tests passing                                 [ ]
Monitor thread confirmed running in terminal         [ ]
All code committed to GitHub                         [ ]
```

---

## Sprint 5 Final Acceptance

Sprint 5 is closed only when every stage acceptance check is complete:

```
Stage 1 - MT5 Connector         [ ]
Stage 2 - Trade Manager         [ ]
All 36 tests passing            [ ]
Demo trade flow verified        [ ]
All code on GitHub              [ ]
```

### Demo Trade Flow Test

Before closing Sprint 5 run this manually:

```python
from src.execution.mt5_connector import connect, send_order, get_open_positions
from src.execution.trade_manager import start, get_position_status, stop
import time

# Step 1 - Connect
connected = connect()
print("Connected:", connected)

# Step 2 - Send a demo order
risk_decision = {
    "signal": "BUY",
    "lot_size": 0.01,
    "entry_price": 0,
    "stop_loss": 2900.0,
    "take_profit": 3100.0,
    "risk_reward": 2.0
}

order = send_order(risk_decision)
print("Order result:", order["status"] if order else "FAILED")

# Step 3 - Start monitor
start()
time.sleep(10)

# Step 4 - Check status
status = get_position_status()
print("Open positions:", status["open_count"])
print("Total profit:  ", status["total_profit"])

# Step 5 - Stop monitor
stop()
```

The output must show:
- `Connected: True`
- Order result of FILLED or simulation equivalent
- Position status returned without error
- Monitor stops cleanly

**If MT5 is not available on Linux — simulation mode output is fully acceptable for Sprint 5 close.**

---

## Linux MT5 Setup Note (Optional)

MetaTrader 5 on Arch Linux requires Wine. To test with a real demo account:

```bash
# Install Wine
sudo pacman -S wine

# Download MT5 installer from your broker website
# Run the installer
wine mt5setup.exe

# The MetaTrader5 Python package connects to Wine MT5 automatically
# No additional configuration needed
```

This step is optional. Simulation mode is sufficient to close Sprint 5.

---

## Important Reminders for the Agent

1. **Demo account only** — never test execution with a live funded account
2. **SL is mandatory** — refuse any order without a stop loss, no exceptions
3. **Trailing stop direction** — for BUY, SL only moves UP. For SELL, SL only moves DOWN. Never backwards.
4. **Partial close is one-time** — track in the database whether partial close has been executed. Never execute twice on the same position.
5. **Thread safety** — the monitor thread accesses MT5 and SQLite concurrently with the main thread. Use threading locks where needed.
6. **Magic number filter** — always filter positions by ORDER_MAGIC so Aurus only manages its own orders, never manual trades placed by the user.

---

*Aurus Sprint 5 - Execution Engine. Every order has a stop loss. No exceptions.*