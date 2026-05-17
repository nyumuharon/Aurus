"""
MT5 Connector Module

Manages the full lifecycle of MetaTrader 5 interaction.
Connects to the broker, places market orders with SL and TP, modifies existing positions,
and closes them. All operations are logged.
"""

import logging
import sqlite3
import os
import traceback
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 not available on this platform")

def _initialize_db():
    """Ensure the execution database and orders table exist."""
    try:
        os.makedirs(os.path.dirname(settings.EXECUTION_DB_PATH), exist_ok=True)
        with sqlite3.connect(settings.EXECUTION_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket        INTEGER,
                    symbol        TEXT NOT NULL,
                    signal        TEXT NOT NULL,
                    lot_size      REAL NOT NULL,
                    entry_price   REAL,
                    stop_loss     REAL NOT NULL,
                    take_profit   REAL NOT NULL,
                    open_time     TEXT NOT NULL,
                    close_time    TEXT,
                    exit_price    REAL,
                    realized_pnl  REAL,
                    status        TEXT DEFAULT 'OPEN',
                    magic         INTEGER,
                    close_reason  TEXT
                );
            ''')
            conn.commit()
    except Exception as e:
        logger.critical(f"Execution DB initialization failed: {e}")

# Initialize DB on module load
_initialize_db()

# Internal mock state for Linux testing
_mock_connected = False
_mock_positions = []
_mock_ticket_counter = 1000000

def connect():
    """Connect to MT5 with credentials from settings."""
    global _mock_connected
    try:
        if not MT5_AVAILABLE:
            logger.warning("MT5 not available. Simulating connection.")
            _mock_connected = True
            return True
            
        if not mt5.initialize(
            login=settings.MT5_LOGIN,
            password=settings.MT5_PASSWORD,
            server=settings.MT5_SERVER,
            timeout=settings.MT5_TIMEOUT_MS
        ):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
            
        logger.info("Connected to MT5")
        return True
    except Exception as e:
        logger.critical(f"Error connecting to MT5: {e}", exc_info=True)
        return False

def disconnect():
    """Cleanly shut down MT5 connection."""
    global _mock_connected
    try:
        if not MT5_AVAILABLE:
            _mock_connected = False
            return
            
        mt5.shutdown()
        logger.info("Disconnected from MT5")
    except Exception as e:
        logger.error(f"Error disconnecting from MT5: {e}")

def is_connected():
    """Check if MT5 connection is alive."""
    if not MT5_AVAILABLE:
        return _mock_connected
        
    try:
        # In mt5, you can check terminal_info() to see if it's connected
        info = mt5.terminal_info()
        if info and info.connected:
            return True
        return False
    except Exception:
        return False

def get_current_price(symbol):
    """Get current bid/ask price for symbol."""
    try:
        if not is_connected():
            return None
            
        if not MT5_AVAILABLE:
            # Mock price
            return {
                "symbol": symbol,
                "bid": 2988.50,
                "ask": 2988.75,
                "spread": 0.25,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.error(f"Failed to get tick for {symbol}")
            return None
            
        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": tick.ask - tick.bid,
            "timestamp": datetime.fromtimestamp(tick.time).strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        return None

def get_symbol_info(symbol):
    """Get symbol trading specifications."""
    try:
        if not is_connected():
            return None
            
        if not MT5_AVAILABLE:
            return {"name": symbol, "trade_mode": 4, "digits": 2, "point": 0.01}
            
        info = mt5.symbol_info(symbol)
        if not info:
            logger.error(f"Failed to get symbol info for {symbol}")
            return None
            
        return {
            "name": info.name,
            "trade_mode": info.trade_mode,
            "digits": info.digits,
            "point": info.point
        }
    except Exception as e:
        logger.error(f"Error getting symbol info: {e}")
        return None

def _save_order_to_db(order_dict):
    try:
        with sqlite3.connect(settings.EXECUTION_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders (ticket, symbol, signal, lot_size, entry_price, stop_loss, take_profit, open_time, status, magic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_dict["ticket"],
                order_dict["symbol"],
                order_dict["signal"],
                order_dict["lot_size"],
                order_dict["entry_price"],
                order_dict["stop_loss"],
                order_dict["take_profit"],
                order_dict["open_time"],
                order_dict["status"],
                order_dict["magic"]
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save order to DB: {e}")

def place_order(signal, lot_size, entry_price, stop_loss, take_profit):
    """Place market order with SL and TP."""
    global _mock_ticket_counter, _mock_positions
    try:
        if not is_connected():
            logger.error("Not connected to MT5")
            return None
            
        if stop_loss is None or stop_loss == 0:
            logger.critical("Order rejected: Missing SL")
            return None
            
        if take_profit is None or take_profit == 0:
            logger.critical("Order rejected: Missing TP")
            return None
            
        if lot_size is None or lot_size <= 0:
            logger.error("Order rejected: Invalid lot size")
            return None
            
        logger.info(f"Placing order: {signal} {lot_size} lot {settings.SYMBOL} at {entry_price}, SL:{stop_loss}, TP:{take_profit}")
        
        if not MT5_AVAILABLE:
            _mock_ticket_counter += 1
            order_dict = {
                "ticket": _mock_ticket_counter,
                "symbol": settings.SYMBOL,
                "signal": signal,
                "lot_size": lot_size,
                "entry_price": entry_price if entry_price else 2988.75,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "open_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "OPEN",
                "magic": settings.SYMBOL_MAGIC
            }
            # Also store in mock positions
            _mock_positions.append({
                "ticket": order_dict["ticket"],
                "symbol": order_dict["symbol"],
                "signal": order_dict["signal"],
                "lot_size": order_dict["lot_size"],
                "entry_price": order_dict["entry_price"],
                "current_price": order_dict["entry_price"],
                "stop_loss": order_dict["stop_loss"],
                "take_profit": order_dict["take_profit"],
                "unrealized_pnl": 0.0,
                "open_time": order_dict["open_time"],
                "magic": order_dict["magic"]
            })
            _save_order_to_db(order_dict)
            return order_dict

        # Real MT5 implementation
        symbol = settings.SYMBOL
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None or not sym_info.visible:
            logger.warning(f"Symbol {symbol} not available")
            return None
            
        order_type = mt5.ORDER_TYPE_BUY if signal.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": settings.SYMBOL_DEVIATION,
            "magic": settings.SYMBOL_MAGIC,
            "comment": "Aurus Order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order rejected: {result.retcode} {mt5.last_error()}")
            return None
            
        order_dict = {
            "ticket": result.order,
            "symbol": symbol,
            "signal": signal,
            "lot_size": lot_size,
            "entry_price": result.price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "open_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "OPEN",
            "magic": settings.SYMBOL_MAGIC
        }
        _save_order_to_db(order_dict)
        return order_dict

    except Exception as e:
        logger.critical(f"Exception in place_order: {e}", exc_info=True)
        return None

def modify_position(ticket, new_sl, new_tp):
    """Modify SL/TP of open position."""
    global _mock_positions
    try:
        if not is_connected():
            return False
            
        if not MT5_AVAILABLE:
            for p in _mock_positions:
                if p["ticket"] == ticket:
                    p["stop_loss"] = new_sl
                    p["take_profit"] = new_tp
                    
                    # Update DB
                    with sqlite3.connect(settings.EXECUTION_DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE orders SET stop_loss=?, take_profit=? WHERE ticket=?", (new_sl, new_tp, ticket))
                        conn.commit()
                    return True
            return False
            
        # Real MT5 implementation
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return False
            
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": float(new_sl),
            "tp": float(new_tp)
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.warning(f"Modify position failed: {result.retcode}")
            return False
            
        # Update DB
        with sqlite3.connect(settings.EXECUTION_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET stop_loss=?, take_profit=? WHERE ticket=?", (new_sl, new_tp, ticket))
            conn.commit()
            
        return True
    except Exception as e:
        logger.error(f"Error modifying position: {e}")
        return False

def close_position(ticket, lot_size):
    """Close all or part of a position."""
    global _mock_positions
    try:
        if not is_connected():
            return False
            
        if not MT5_AVAILABLE:
            idx = -1
            for i, p in enumerate(_mock_positions):
                if p["ticket"] == ticket:
                    idx = i
                    break
            if idx >= 0:
                p = _mock_positions[idx]
                if lot_size >= p["lot_size"]:
                    _mock_positions.pop(idx)
                    status = "CLOSED"
                else:
                    p["lot_size"] -= lot_size
                    status = "OPEN"
                    
                # Update DB
                with sqlite3.connect(settings.EXECUTION_DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE orders SET status=?, close_time=?, exit_price=? WHERE ticket=?", 
                                  (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p["current_price"], ticket))
                    conn.commit()
                return True
            return False
            
        # Real MT5 implementation
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return False
            
        pos = pos[0]
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pos.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": float(lot_size),
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": settings.SYMBOL_DEVIATION,
            "magic": settings.SYMBOL_MAGIC,
            "comment": "Aurus Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Close position failed: {result.retcode}")
            return False
            
        # Partial close check
        status = "CLOSED" if abs(pos.volume - lot_size) < 0.001 else "OPEN"
            
        with sqlite3.connect(settings.EXECUTION_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET status=?, close_time=?, exit_price=? WHERE ticket=?", 
                          (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), price, ticket))
            conn.commit()
            
        return True
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return False

def get_open_positions():
    """Get all open positions for Aurus magic number."""
    try:
        if not is_connected():
            return []
            
        if not MT5_AVAILABLE:
            return _mock_positions
            
        positions = mt5.positions_get(magic=settings.SYMBOL_MAGIC)
        if not positions:
            return []
            
        res = []
        for p in positions:
            res.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "signal": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "lot_size": p.volume,
                "entry_price": p.price_open,
                "current_price": p.price_current,
                "stop_loss": p.sl,
                "take_profit": p.tp,
                "unrealized_pnl": p.profit,
                "open_time": datetime.fromtimestamp(p.time).strftime("%Y-%m-%d %H:%M:%S")
            })
        return res
    except Exception as e:
        logger.error(f"Error getting open positions: {e}")
        return []

def get_position_by_ticket(ticket):
    """Get single position details by ticket number."""
    try:
        positions = get_open_positions()
        for p in positions:
            if p["ticket"] == ticket:
                return p
        return None
    except Exception as e:
        logger.error(f"Error getting position by ticket: {e}")
        return None
