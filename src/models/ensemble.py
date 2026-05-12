"""
Ensemble Voting Engine Module
=============================
Collects signals from all four models, applies weighted voting, and outputs one clean final signal.
"""

import logging
import datetime
from typing import Dict, Any, Optional

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "lstm":          0.30,
    "tft":           0.30,
    "random_forest": 0.20,
    "smc_detector":  0.20
}

SIGNAL_MAP = {
    "BUY": 1,
    "BULLISH": 1,
    "SELL": -1,
    "BEARISH": -1,
    "HOLD": 0,
    "NEUTRAL": 0
}


def collect_signals() -> Dict[str, Optional[Dict[str, Any]]]:
    """Get signals from all 4 models.
    
    Gracefully isolates any single model evaluation failures.
    """
    signals = {}
    
    # 1. LSTM
    try:
        from src.models import lstm_model
        signals["lstm"] = lstm_model.get_signal()
    except Exception as e:
        logger.warning(f"Failed to collect LSTM signal: {e}")
        signals["lstm"] = None
        
    # 2. TFT
    try:
        from src.models import tft_model
        signals["tft"] = tft_model.get_signal()
    except Exception as e:
        logger.warning(f"Failed to collect TFT signal: {e}")
        signals["tft"] = None
        
    # 3. Random Forest
    try:
        from src.models import random_forest
        signals["random_forest"] = random_forest.get_signal()
    except Exception as e:
        logger.warning(f"Failed to collect Random Forest signal: {e}")
        signals["random_forest"] = None
        
    # 4. SMC Detector
    try:
        from src.models import smc_detector
        signals["smc_detector"] = smc_detector.get_signal()
    except Exception as e:
        logger.warning(f"Failed to collect SMC signal: {e}")
        signals["smc_detector"] = None
        
    return signals


def calculate_weighted_score(signals: Dict[str, Optional[Dict[str, Any]]]) -> float:
    """Apply weights and compute score.
    
    Redistributes weights if any single model fails or is missing.
    """
    if not signals:
        return 0.0
        
    active_weights = {}
    valid_signals = {}
    
    for model_name, sig_dict in signals.items():
        if sig_dict and isinstance(sig_dict, dict) and "signal" in sig_dict and "confidence" in sig_dict:
            active_weights[model_name] = DEFAULT_WEIGHTS.get(model_name, 0.0)
            valid_signals[model_name] = sig_dict
            
    total_weight = sum(active_weights.values())
    if total_weight <= 0.0:
        logger.critical("All models failed or provided 0 weight. Returning 0.0 score.")
        return 0.0
        
    weighted_score = 0.0
    for model_name, sig_dict in valid_signals.items():
        # Redistribute weight proportionally
        effective_weight = active_weights[model_name] / total_weight
        sig_str = sig_dict["signal"]
        conf = float(sig_dict["confidence"])
        mapped_val = SIGNAL_MAP.get(sig_str, 0)
        
        weighted_score += mapped_val * conf * effective_weight
        
    return float(weighted_score)


def determine_signal(score: float) -> str:
    """Convert score to BUY/SELL/NO_TRADE based on threshold."""
    thresh = getattr(settings, 'ENSEMBLE_THRESHOLD', 0.60)
    if score >= thresh:
        return "BUY"
    elif score <= -thresh:
        return "SELL"
    else:
        return "NO_TRADE"


def log_signal(signal_dict: Dict[str, Any]) -> None:
    """Log signal details for audit trail."""
    if not signal_dict:
        return
    logger.info(
        f"Ensemble Audit Trail | Final: {signal_dict.get('final_signal')} | "
        f"Score: {signal_dict.get('weighted_score'):.4f} | "
        f"Passed to Validator: {signal_dict.get('passed_to_validator')}"
    )


def get_ensemble_signal() -> Dict[str, Any]:
    """Full pipeline — collect, score, decide."""
    signals = collect_signals()
    score = calculate_weighted_score(signals)
    final_sig = determine_signal(score)
    
    thresh = getattr(settings, 'ENSEMBLE_THRESHOLD', 0.60)
    passed = (final_sig in {"BUY", "SELL"})
    
    # Format individual signals tracking block cleanly
    indiv = {}
    for m in ["lstm", "tft", "random_forest", "smc_detector"]:
        s_dict = signals.get(m)
        if s_dict and isinstance(s_dict, dict):
            indiv[m] = {
                "signal": s_dict.get("signal", "HOLD"),
                "confidence": float(s_dict.get("confidence", 0.50))
            }
        else:
            indiv[m] = None
            
    # If all models failed, guarantee NO_TRADE is handled gracefully per requirements
    if all(v is None for v in indiv.values()):
        logger.critical("Ensemble execution blocked: All incoming model signals failed.")
        final_sig = "NO_TRADE"
        score = 0.0
        passed = False
        
    result = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "final_signal": final_sig,
        "weighted_score": score,
        "threshold": thresh,
        "individual_signals": indiv,
        "passed_to_validator": passed
    }
    
    log_signal(result)
    return result
