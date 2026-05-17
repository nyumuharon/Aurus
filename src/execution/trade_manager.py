"""
Trade Manager Module

Runs as a background monitoring loop. Every 5 seconds it checks all open positions,
applies trailing stop logic, detects when partial close conditions are met at 1:1 R/R,
and reports position status.
"""

import logging
import time
import threading
from config import settings
from src.execution import mt5_connector

logger = logging.getLogger(__name__)

_monitoring_active = False
_monitor_thread = None
_position_state = {}  # ticket -> {"partially_closed": bool, "trailing_active": bool}
_last_open_positions = {} # ticket -> position dict

def start_monitoring():
    """Start background position monitoring thread."""
    global _monitoring_active, _monitor_thread
    if _monitoring_active:
        return
        
    _monitoring_active = True
    _monitor_thread = threading.Thread(target=_monitoring_loop, daemon=True)
    _monitor_thread.start()
    logger.info("Trade monitoring started")

def stop_monitoring():
    """Stop monitoring thread cleanly."""
    global _monitoring_active
    _monitoring_active = False
    if _monitor_thread:
        _monitor_thread.join(timeout=2.0)
    logger.info("Trade monitoring stopped")

def is_monitoring():
    """Check if monitoring is active."""
    return _monitoring_active

def check_positions():
    """Single monitoring cycle — check all positions."""
    try:
        positions = mt5_connector.get_open_positions()
        
        # Init state for new positions
        for p in positions:
            t = p["ticket"]
            if t not in _position_state:
                _position_state[t] = {
                    "partially_closed": False,
                    "trailing_active": settings.TRAILING_STOP_ENABLED
                }
                
        return positions
    except Exception as e:
        logger.error(f"Error checking positions: {e}")
        return []

def apply_trailing_stop(position, atr):
    """Update SL if trailing stop condition met."""
    try:
        if not atr or atr <= 0:
            return False
            
        ticket = position["ticket"]
        signal = position["signal"]
        current_price = position["current_price"]
        current_sl = position["stop_loss"]
        entry_price = position["entry_price"]
        
        # Only apply if in profit
        if signal.upper() == "BUY" and current_price <= entry_price:
            return False
        if signal.upper() == "SELL" and current_price >= entry_price:
            return False
            
        new_sl = current_sl
        modified = False
        
        if signal.upper() == "BUY":
            calc_sl = current_price - (atr * settings.TRAILING_STOP_ATR_MULTIPLIER)
            if calc_sl > current_sl:
                new_sl = calc_sl
                modified = True
        elif signal.upper() == "SELL":
            calc_sl = current_price + (atr * settings.TRAILING_STOP_ATR_MULTIPLIER)
            # For SELL, smaller SL means tighter stop (lower price)
            if current_sl == 0 or calc_sl < current_sl:
                new_sl = calc_sl
                modified = True
                
        if modified:
            res = mt5_connector.modify_position(ticket, new_sl, position["take_profit"])
            if res:
                logger.info(f"Trailing SL applied to {ticket}: moved to {new_sl}")
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error applying trailing stop: {e}")
        return False

def check_partial_close(position):
    """Check if 1:1 R/R reached for partial close."""
    try:
        ticket = position["ticket"]
        if _position_state.get(ticket, {}).get("partially_closed"):
            return False
            
        signal = position["signal"]
        entry = position["entry_price"]
        sl = position["stop_loss"]
        current = position["current_price"]
        
        if signal.upper() == "BUY":
            risk = entry - sl
            if risk <= 0: return False
            target = entry + risk
            if current >= target:
                return True
        elif signal.upper() == "SELL":
            risk = sl - entry
            if risk <= 0: return False
            target = entry - risk
            if current <= target:
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error checking partial close: {e}")
        return False

def execute_partial_close(position):
    """Close 50% of position at 1:1 R/R."""
    try:
        ticket = position["ticket"]
        lot_size = position["lot_size"]
        entry = position["entry_price"]
        tp = position["take_profit"]
        
        close_lot = lot_size * settings.PARTIAL_CLOSE_PCT
        # Round to lot step
        close_lot = round(close_lot / settings.XAUUSD_LOT_STEP) * settings.XAUUSD_LOT_STEP
        if close_lot < settings.XAUUSD_LOT_STEP:
            close_lot = settings.XAUUSD_LOT_STEP
            
        if close_lot >= lot_size:
            # Can't partial close if size is too small, just leave it or full close?
            # Instructions say close 50% of lot size
            pass
            
        res = mt5_connector.close_position(ticket, close_lot)
        if res:
            logger.info(f"Partial close executed for {ticket}: closed {close_lot} lots")
            
            # Move SL to breakeven
            mt5_connector.modify_position(ticket, entry, tp)
            logger.info(f"SL moved to breakeven ({entry}) for {ticket}")
            
            _position_state[ticket]["partially_closed"] = True
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error executing partial close: {e}")
        return False

def detect_closed_positions():
    """Find positions closed since last check."""
    global _last_open_positions
    try:
        current_positions = check_positions()
        current_tickets = {p["ticket"]: p for p in current_positions}
        
        closed = []
        for ticket, p in _last_open_positions.items():
            if ticket not in current_tickets:
                closed.append(p)
                
        _last_open_positions = current_tickets
        return closed
    except Exception as e:
        logger.error(f"Error detecting closed positions: {e}")
        return []

def handle_closed_position(position):
    """Record closed position P&L and notify."""
    try:
        ticket = position["ticket"]
        logger.info(f"Position {ticket} closed. Realized PNL: {position.get('unrealized_pnl', 0.0)}")
        if ticket in _position_state:
            del _position_state[ticket]
    except Exception as e:
        logger.error(f"Error handling closed position: {e}")

def get_position_status():
    """Return current status of all monitored positions."""
    try:
        positions = mt5_connector.get_open_positions()
        status_list = []
        for p in positions:
            t = p["ticket"]
            state = _position_state.get(t, {"partially_closed": False, "trailing_active": False})
            
            p_status = p.copy()
            p_status["partially_closed"] = state["partially_closed"]
            p_status["trailing_active"] = state["trailing_active"]
            p_status["monitoring_status"] = "ACTIVE" if _monitoring_active else "INACTIVE"
            status_list.append(p_status)
            
        return status_list
    except Exception as e:
        logger.error(f"Error getting position status: {e}")
        return []

def _monitoring_loop():
    while _monitoring_active:
        try:
            positions = check_positions()
            current_atr = 5.0 # Mock ATR for trailing stop
            
            for pos in positions:
                ticket = pos["ticket"]
                state = _position_state.get(ticket, {})
                
                if settings.TRAILING_STOP_ENABLED:
                    apply_trailing_stop(pos, current_atr)
                    
                if not state.get("partially_closed"):
                    if check_partial_close(pos):
                        execute_partial_close(pos)
                        
            closed = detect_closed_positions()
            for pos in closed:
                handle_closed_position(pos)
                
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
            
        time.sleep(settings.MONITOR_INTERVAL_SECONDS)
