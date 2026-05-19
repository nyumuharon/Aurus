# Aurus — Sprint 4 Agent Build Plan
## Risk Manager — Staged Construction

**Version:** 1.0
**Sprint:** 4 of 6
**Senior Principal Engineer:** Claude
**Lead Engineer:** Haron
**Goal:** Build the Risk Manager that enforces all capital protection rules. No trade reaches the execution engine without passing through this layer. Rules are absolute — no model, no validator, no external input can override them.

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
- **Risk rules are ABSOLUTE — they cannot be overridden by any other layer**
- **When in doubt, BLOCK the trade — never approve on uncertainty**
- Every risk decision must be logged with full context

---

## Architecture Reminder

```
Validation Result (Layer 3)
          |
          v
[ risk_manager.py ]     <- Stage 1
  - Check daily drawdown
  - Check total drawdown
  - Check max trades per day
  - Calculate ATR position size
  - Approve or block trade
          |
          v
[ position_sizer.py ]   <- Stage 2
  - Calculate lot size from ATR
  - Validate SL and TP levels
  - Enforce minimum R/R ratio
          |
          v
Layer 5 - Execution Engine (Sprint 5)
```

---

## File Structure Being Built

```
aurus/
  src/
    risk/
      __init__.py
      risk_manager.py       <- Stage 1
      position_sizer.py     <- Stage 2
  tests/
    test_risk_manager.py    <- Stage 1 test
    test_position_sizer.py  <- Stage 2 test
  data/
    risk.db                 <- SQLite for risk state
```

---

## Constants to Add to `config/settings.py`

Append the following block to the bottom of the existing `settings.py`:

```python
# -- Sprint 4 - Risk Manager ------------------------------------------

# Capital protection rules (prop firm standard)
MAX_DAILY_LOSS_PCT = 0.05        # 5% max daily loss
MAX_TOTAL_DRAWDOWN_PCT = 0.10    # 10% max total drawdown
MAX_TRADES_PER_DAY = 3           # maximum trades per calendar day
RISK_PER_TRADE_PCT = 0.01        # 1% account risk per trade
MIN_RISK_REWARD_RATIO = 2.0      # minimum 1:2 R/R

# ATR position sizing
ATR_PERIOD = 14                  # ATR calculation period
ATR_SL_MULTIPLIER = 1.5          # stop loss = ATR * 1.5
ATR_TP_MULTIPLIER = 3.0          # take profit = ATR * 3.0 (1:2 R/R)

# XAU/USD pip value
XAUUSD_PIP_VALUE = 1.0           # $1 per 0.01 lot per pip on XAU/USD
XAUUSD_LOT_STEP = 0.01           # minimum lot increment

# Risk database
RISK_DB_PATH = "data/risk.db"
RISK_LOG_FILE = "logs/risk.log"

# Account (set real value before live trading)
ACCOUNT_BALANCE = 10000.0        # default demo account balance
```

---

## Stage 1 - Risk Manager (`risk_manager.py`)

**Build this first. Position sizer depends on it.**

### What this module does

Enforces all capital protection rules before any trade is approved. Maintains a daily trade counter and drawdown tracker in SQLite. Returns APPROVED with calculated position parameters or BLOCKED with a reason. This is the final gate before execution.

### File to create

`src/risk/risk_manager.py`

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `initialize_db()` | Create SQLite tables for risk tracking | `None` |
| `get_daily_stats()` | Get today's trade count and P&L from DB | `dict` |
| `get_total_drawdown()` | Calculate total drawdown from account peak | `float` |
| `check_daily_loss(daily_pnl)` | Check if daily loss limit is breached | `True` (safe) or `False` (breached) |
| `check_total_drawdown(drawdown)` | Check if total drawdown limit is breached | `True` (safe) or `False` (breached) |
| `check_trade_count(trade_count)` | Check if max trades per day is reached | `True` (safe) or `False` (reached) |
| `check_high_impact_window(calendar_data)` | Check if high impact event is imminent | `True` (safe) or `False` (blocked) |
| `evaluate(validation_result, market_snapshot)` | Run all checks and return risk decision | `dict` |
| `record_trade_open(trade_id, signal, lot_size, entry_price, sl, tp)` | Log trade open to SQLite | `None` |
| `record_trade_close(trade_id, exit_price, pnl)` | Log trade close and update daily P&L | `None` |
| `get_default_block(reason)` | Return standard BLOCKED result | `dict` |

### Output format of `evaluate()`

```python
{
    "timestamp": "2026-03-01 10:00:00",
    "signal": "BUY",
    "decision": "APPROVED",          # "APPROVED" or "BLOCKED"
    "reason": "All risk checks passed",
    "lot_size": 0.05,                # calculated by position sizer
    "entry_price": 2988.75,
    "stop_loss": 2982.63,            # entry - (ATR * 1.5)
    "take_profit": 3001.00,          # entry + (ATR * 3.0)
    "risk_reward": 2.05,
    "daily_trade_count": 1,
    "daily_pnl": 0.0,
    "total_drawdown_pct": 0.0,
    "account_balance": 10000.0,
    "passed_to_execution": True      # True only if APPROVED
}
```

### Output format of `get_default_block()`

```python
{
    "timestamp": "2026-03-01 10:00:00",
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
```

### SQLite Schema

Create these tables in `data/risk.db`:

```sql
-- Tracks every trade opened and closed
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

-- Tracks daily summary for drawdown calculation
CREATE TABLE IF NOT EXISTS daily_summary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL UNIQUE,
    trade_count   INTEGER DEFAULT 0,
    daily_pnl     REAL DEFAULT 0.0,
    peak_balance  REAL NOT NULL,
    close_balance REAL
);
```

### Rule Evaluation Order

Rules must be checked in this exact order. Stop at first failure:

```
1. Check validation_result.validated == True
   If False -> BLOCK ("Trade not validated by AI")

2. Check high impact event window
   If True -> BLOCK ("High impact event imminent")

3. Check total drawdown < MAX_TOTAL_DRAWDOWN_PCT
   If breached -> BLOCK ("Total drawdown limit reached - system halted")

4. Check daily loss < MAX_DAILY_LOSS_PCT
   If breached -> BLOCK ("Daily loss limit reached")

5. Check trade count < MAX_TRADES_PER_DAY
   If reached -> BLOCK ("Maximum trades per day reached")

6. Calculate position size
   If lot_size <= 0 -> BLOCK ("Position size calculation failed")

7. Validate R/R ratio >= MIN_RISK_REWARD_RATIO
   If below -> BLOCK ("Risk/reward ratio below minimum")

8. All checks passed -> APPROVED
```

### Error handling rules

- If SQLite connection fails -> log critical, return `get_default_block("Database error")`
- If market snapshot missing price data -> log error, return `get_default_block("Missing price data")`
- If any check throws exception -> log critical with traceback, return `get_default_block("Unexpected error")`
- Never raise — always return a dict

### Stage 1 Test (`tests/test_risk_manager.py`)

```
1.  initialize_db() creates required tables without error
2.  get_daily_stats() returns dict with trade_count and daily_pnl keys
3.  get_daily_stats() returns zero values on fresh day
4.  check_daily_loss() returns True when daily loss is below limit
5.  check_daily_loss() returns False when daily loss exceeds 5%
6.  check_total_drawdown() returns True when drawdown is below limit
7.  check_total_drawdown() returns False when drawdown exceeds 10%
8.  check_trade_count() returns True when count is below max
9.  check_trade_count() returns False when count reaches max (3)
10. check_high_impact_window() returns False when no high impact events
11. check_high_impact_window() returns True when high impact event imminent
12. evaluate() returns APPROVED dict when all checks pass
13. evaluate() returns BLOCKED when validation_result.validated is False
14. evaluate() returns BLOCKED when daily loss limit is breached
15. evaluate() returns BLOCKED when total drawdown is breached
16. evaluate() returns BLOCKED when max trades reached
17. evaluate() returns BLOCKED when high impact event imminent
18. record_trade_open() writes to trades table without error
19. record_trade_close() updates trade record and daily P&L correctly
20. get_default_block() returns correct structure with passed_to_execution=False
```

### Stage 1 Acceptance Check

```
src/risk/__init__.py created                          [ ]
risk_manager.py exists in src/risk/                   [ ]
All 11 functions implemented                          [ ]
All functions have docstrings                         [ ]
SQLite tables created correctly                       [ ]
Rule evaluation order is correct                      [ ]
All 20 tests passing                                  [ ]
Sample evaluate() result prints to terminal           [ ]
```

**Do not proceed to Stage 2 until all are checked.**

---

## Stage 2 - Position Sizer (`position_sizer.py`)

**Depends on:** Stage 1 complete and accepted

### What this module does

Calculates the correct lot size for each trade based on account balance, ATR volatility, and the 1% risk rule. Also calculates stop loss and take profit levels and validates the risk/reward ratio. Called by the risk manager during trade evaluation.

### File to create

`src/risk/position_sizer.py`

### Position Sizing Formula

```
stop_loss_distance = ATR(14) * ATR_SL_MULTIPLIER (1.5)
take_profit_distance = ATR(14) * ATR_TP_MULTIPLIER (3.0)

risk_amount = account_balance * RISK_PER_TRADE_PCT (0.01)

lot_size = risk_amount / (stop_loss_distance * XAUUSD_PIP_VALUE / XAUUSD_LOT_STEP)

lot_size = round down to nearest XAUUSD_LOT_STEP (0.01)
lot_size = minimum 0.01, maximum 10.0
```

### SL and TP Calculation

```
For BUY signal:
  stop_loss   = entry_price - stop_loss_distance
  take_profit = entry_price + take_profit_distance

For SELL signal:
  stop_loss   = entry_price + stop_loss_distance
  take_profit = entry_price - take_profit_distance
```

### Risk/Reward Validation

```
risk_reward = take_profit_distance / stop_loss_distance

Must be >= MIN_RISK_REWARD_RATIO (2.0)
If below -> return None to signal invalid setup
```

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `calculate_atr(candles, period)` | Calculate ATR from list of OHLCV candles | `float` or `None` |
| `calculate_lot_size(account_balance, stop_loss_distance)` | Calculate lot size using 1% risk rule | `float` or `None` |
| `calculate_sl_tp(signal, entry_price, atr)` | Calculate SL and TP from ATR | `dict` or `None` |
| `validate_risk_reward(sl_distance, tp_distance)` | Check R/R meets minimum | `True` or `False` |
| `get_position_parameters(signal, entry_price, candles, account_balance)` | Full position sizing pipeline | `dict` or `None` |

### Output format of `get_position_parameters()`

```python
{
    "lot_size": 0.05,
    "entry_price": 2988.75,
    "stop_loss": 2982.63,
    "take_profit": 3001.00,
    "stop_loss_distance": 6.12,
    "take_profit_distance": 12.25,
    "risk_reward": 2.00,
    "atr": 4.08,
    "risk_amount": 100.0,
    "account_balance": 10000.0
}
```

### Error handling rules

- If candles list has fewer than ATR_PERIOD candles -> log warning, return `None`
- If ATR calculation produces zero or negative -> log error, return `None`
- If calculated lot size is below minimum -> use minimum lot size (0.01)
- If calculated lot size exceeds maximum -> use maximum lot size (10.0)
- If R/R ratio below minimum -> log warning, return `None`
- Never raise — always return dict or None

### Stage 2 Test (`tests/test_position_sizer.py`)

```
1.  calculate_atr() returns correct float for known OHLCV input
2.  calculate_atr() returns None for insufficient candles
3.  calculate_atr() returns None for empty candle list
4.  calculate_lot_size() returns correct lot for known inputs
5.  calculate_lot_size() returns minimum lot when calculated size is too small
6.  calculate_lot_size() returns maximum lot when calculated size is too large
7.  calculate_lot_size() returns lot rounded to correct step size
8.  calculate_sl_tp() returns correct SL below entry for BUY signal
9.  calculate_sl_tp() returns correct TP above entry for BUY signal
10. calculate_sl_tp() returns correct SL above entry for SELL signal
11. calculate_sl_tp() returns correct TP below entry for SELL signal
12. validate_risk_reward() returns True for ratio >= 2.0
13. validate_risk_reward() returns False for ratio < 2.0
14. get_position_parameters() returns dict with all required keys
15. get_position_parameters() returns None when ATR calculation fails
16. get_position_parameters() returns None when R/R is below minimum
17. All price values are positive floats
18. lot_size is always a multiple of XAUUSD_LOT_STEP
```

### Stage 2 Acceptance Check

```
position_sizer.py exists in src/risk/                [ ]
All 5 functions implemented                          [ ]
ATR calculation mathematically correct               [ ]
Lot size calculation follows 1% risk rule            [ ]
SL/TP correct for both BUY and SELL                  [ ]
R/R validation working correctly                     [ ]
All 18 tests passing                                 [ ]
Sample position parameters print to terminal         [ ]
All code committed to GitHub                         [ ]
```

---

## Sprint 4 Final Acceptance

Sprint 4 is closed only when every stage acceptance check is complete:

```
Stage 1 - Risk Manager          [ ]
Stage 2 - Position Sizer        [ ]
All 38 tests passing            [ ]
Live end-to-end risk check      [ ]
All code on GitHub              [ ]
```

### End-to-End Risk Check

Before closing Sprint 4 run this manually:

```python
from src.risk.risk_manager import evaluate

# Mock a passing validation result
validation_result = {
    "timestamp": "2026-03-01 10:00:00",
    "signal": "BUY",
    "validated": True,
    "decision": "YES",
    "reason": "Signal aligns with market context"
}

# Mock market snapshot with price data
market_snapshot = {
    "price": {
        "latest_candle": {"close": 2988.75},
        "candles_1m": [
            {"open": 2985.0, "high": 2992.0,
             "low": 2983.0, "close": 2988.75, "volume": 100}
            for _ in range(20)
        ]
    },
    "calendar": {
        "high_impact_window": False,
        "events_today": []
    }
}

result = evaluate(validation_result, market_snapshot)

print("Decision:    ", result["decision"])
print("Lot size:    ", result["lot_size"])
print("Stop loss:   ", result["stop_loss"])
print("Take profit: ", result["take_profit"])
print("R/R ratio:   ", result["risk_reward"])
print("Reason:      ", result["reason"])
```

The output must show:
- `decision` is `"APPROVED"` or `"BLOCKED"` with a clear reason
- `lot_size` is a positive float rounded to 0.01
- `stop_loss` is below entry for BUY signal
- `take_profit` is above entry for BUY signal
- `risk_reward` is >= 2.0

When this runs cleanly — Sprint 4 is closed.

---

## Important Reminders for the Agent

1. **Rules are absolute** — no exceptions, no overrides, no special cases
2. **Evaluation order matters** — check in the exact order specified. Total drawdown before daily loss. Daily loss before trade count.
3. **Total drawdown triggers system halt** — when total drawdown exceeds 10%, log critical and block ALL subsequent trades for the rest of the session, not just the current one
4. **SQLite is the source of truth** — never calculate drawdown or trade count from memory. Always read from the database
5. **Position size must be recalculated every trade** — ATR changes with each candle. Never reuse a previous lot size
6. **Test with mocks** — do not require live MT5 data for unit tests. Use synthetic OHLCV candle lists

---

*Aurus Sprint 4 - Risk Manager. Rules first. Always.*
