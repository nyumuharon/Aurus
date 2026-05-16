"""
Position Sizer Module

Calculates the correct lot size for each trade based on account balance,
ATR volatility, and the 1% risk rule. Calculates stop loss and take profit levels
and validates the risk/reward ratio.
"""

import logging
import math
from config import settings

logger = logging.getLogger(__name__)

def calculate_atr(candles, period):
    """
    Calculate ATR from a list of OHLCV candles.
    """
    try:
        if not candles or len(candles) < period:
            logger.warning(f"Insufficient candles for ATR. Need {period}, got {len(candles) if candles else 0}")
            return None
            
        # Standard ATR calculation
        # TR = max((high - low), abs(high - close_prev), abs(low - close_prev))
        # ATR = SMA(TR, period)
        
        # Ensure we have at least period + 1 candles to compute period TRs,
        # or just compute TR for the last `period` candles. Usually ATR needs period + 1 
        # to have a previous close for the first TR. Let's compute TR for all available, then take SMA of last `period`.
        
        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            prev = candles[i-1]
            high = current.get("high", 0.0)
            low = current.get("low", 0.0)
            close_prev = prev.get("close", 0.0)
            
            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            true_ranges.append(tr)
            
        if len(true_ranges) < period:
            logger.warning("Insufficient true ranges for ATR calculation")
            return None
            
        atr = sum(true_ranges[-period:]) / period
        
        if atr <= 0:
            logger.error(f"ATR calculation produced non-positive value: {atr}")
            return None
            
        return atr
        
    except Exception as e:
        logger.error(f"Error calculating ATR: {e}")
        return None

def calculate_lot_size(account_balance, stop_loss_distance):
    """
    Calculate lot size using 1% risk rule.
    """
    try:
        if not account_balance or account_balance <= 0:
            return None
        if not stop_loss_distance or stop_loss_distance <= 0:
            return None
            
        risk_amount = account_balance * settings.RISK_PER_TRADE_PCT
        
        pip_value = settings.XAUUSD_PIP_VALUE
        lot_step = settings.XAUUSD_LOT_STEP
        
        # lot_size = risk_amount / (stop_loss_distance * XAUUSD_PIP_VALUE / XAUUSD_LOT_STEP)
        # Using exact formula from spec
        lot_size = risk_amount / (stop_loss_distance * pip_value / lot_step)
        
        # Round down to nearest lot_step
        # To avoid floating point issues, use integer math for step
        steps = math.floor(lot_size / lot_step)
        lot_size = steps * lot_step
        
        # Boundaries
        if lot_size < 0.01:
            return 0.01
        if lot_size > 10.0:
            return 10.0
            
        return lot_size
        
    except Exception as e:
        logger.error(f"Error calculating lot size: {e}")
        return None

def calculate_sl_tp(signal, entry_price, atr):
    """
    Calculate SL and TP from ATR.
    """
    try:
        sl_dist = atr * settings.ATR_SL_MULTIPLIER
        tp_dist = atr * settings.ATR_TP_MULTIPLIER
        
        if signal.upper() == "BUY":
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        elif signal.upper() == "SELL":
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
        else:
            return None
            
        return {
            "stop_loss": sl,
            "take_profit": tp,
            "stop_loss_distance": sl_dist,
            "take_profit_distance": tp_dist
        }
    except Exception as e:
        logger.error(f"Error calculating SL/TP: {e}")
        return None

def validate_risk_reward(sl_distance, tp_distance):
    """
    Check R/R meets minimum.
    """
    try:
        if not sl_distance or sl_distance <= 0:
            return False
            
        rr = tp_distance / sl_distance
        return rr >= settings.MIN_RISK_REWARD_RATIO
    except Exception as e:
        logger.error(f"Error validating R/R: {e}")
        return False

def get_position_parameters(signal, entry_price, candles, account_balance):
    """
    Full position sizing pipeline.
    """
    try:
        if not signal or not entry_price or not account_balance:
            return None
            
        atr = calculate_atr(candles, settings.ATR_PERIOD)
        if atr is None:
            return None
            
        sl_tp = calculate_sl_tp(signal, entry_price, atr)
        if not sl_tp:
            return None
            
        sl_dist = sl_tp["stop_loss_distance"]
        tp_dist = sl_tp["take_profit_distance"]
        
        if not validate_risk_reward(sl_dist, tp_dist):
            logger.warning("R/R ratio below minimum")
            return None
            
        lot_size = calculate_lot_size(account_balance, sl_dist)
        if lot_size is None:
            return None
            
        rr = tp_dist / sl_dist if sl_dist > 0 else 0
        risk_amount = account_balance * settings.RISK_PER_TRADE_PCT
        
        return {
            "lot_size": lot_size,
            "entry_price": entry_price,
            "stop_loss": round(sl_tp["stop_loss"], 2),
            "take_profit": round(sl_tp["take_profit"], 2),
            "stop_loss_distance": round(sl_dist, 2),
            "take_profit_distance": round(tp_dist, 2),
            "risk_reward": round(rr, 2),
            "atr": round(atr, 2),
            "risk_amount": round(risk_amount, 2),
            "account_balance": account_balance
        }
        
    except Exception as e:
        logger.error(f"Error in get_position_parameters: {e}")
        return None
