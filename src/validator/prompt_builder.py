"""
Prompt Builder Module

Takes raw data from the ensemble signal and the Data Manager market snapshot
and builds a single structured prompt string ready to send to Qwen3:8b.
Contains zero AI logic — it only formats data into text.
"""

import logging
from config import settings

logger = logging.getLogger(__name__)

def validate_inputs(ensemble_signal, market_snapshot):
    """
    Check all required fields exist in the inputs.
    
    Args:
        ensemble_signal (dict): The ensemble signal dictionary.
        market_snapshot (dict): The market snapshot dictionary.
        
    Returns:
        bool: True if valid, False otherwise.
    """
    if ensemble_signal is None or market_snapshot is None:
        return False
        
    if not isinstance(ensemble_signal, dict) or not isinstance(market_snapshot, dict):
        return False
        
    required_signal_keys = ["final_signal", "weighted_score", "individual_signals"]
    for key in required_signal_keys:
        if key not in ensemble_signal:
            return False
            
    required_snapshot_keys = ["price", "news", "dxy", "calendar"]
    for key in required_snapshot_keys:
        if key not in market_snapshot:
            return False
            
    if "latest_candle" not in market_snapshot.get("price", {}):
        return False
        
    if "close" not in market_snapshot["price"]["latest_candle"]:
        return False
        
    if "trend" not in market_snapshot.get("dxy", {}):
        return False
        
    return True

def format_signal_section(ensemble_signal):
    """
    Format the signal and score section.
    Note: ENTRY PRICE and DXY BIAS are handled in build_prompt.
    
    Args:
        ensemble_signal (dict): The ensemble signal dictionary.
        
    Returns:
        str: Formatted signal string.
    """
    try:
        final_signal = ensemble_signal.get("final_signal", "UNKNOWN")
        score = ensemble_signal.get("weighted_score", 0.0)
        return f"SIGNAL: {final_signal}\nCONFIDENCE SCORE: {score:.2f}"
    except Exception as e:
        logger.error(f"Error formatting signal section: {e}")
        return ""

def format_model_section(ensemble_signal):
    """
    Format individual model votes section.
    
    Args:
        ensemble_signal (dict): The ensemble signal dictionary.
        
    Returns:
        str: Formatted model section string.
    """
    try:
        models = ensemble_signal.get("individual_signals", {})
        lstm = models.get("lstm", {"signal": "UNKNOWN", "confidence": 0.0})
        tft = models.get("tft", {"signal": "UNKNOWN", "confidence": 0.0})
        rf = models.get("random_forest", {"signal": "UNKNOWN", "confidence": 0.0})
        smc = models.get("smc_detector", {"signal": "UNKNOWN", "confidence": 0.0})
        
        section = (
            "MODEL AGREEMENT:\n"
            f"  - LSTM:          {lstm.get('signal', 'UNKNOWN')} ({lstm.get('confidence', 0.0):.0%})\n"
            f"  - TFT:           {tft.get('signal', 'UNKNOWN')} ({tft.get('confidence', 0.0):.0%})\n"
            f"  - Random Forest: {rf.get('signal', 'UNKNOWN')} ({rf.get('confidence', 0.0):.0%})\n"
            f"  - SMC Detector:  {smc.get('signal', 'UNKNOWN')} ({smc.get('confidence', 0.0):.0%})"
        )
        return section
    except Exception as e:
        logger.error(f"Error formatting model section: {e}")
        return ""

def format_news_section(news_list):
    """
    Format top headlines section.
    
    Args:
        news_list (list): List of news dictionaries.
        
    Returns:
        str: Formatted news section string.
    """
    try:
        if not news_list or not isinstance(news_list, list):
            return "RECENT NEWS:\n  - No recent news available"
            
        max_headlines = getattr(settings, "PROMPT_MAX_HEADLINES", 3)
        section = "RECENT NEWS:\n"
        
        count = 0
        for item in news_list:
            if count >= max_headlines:
                break
            headline = item.get("headline") if isinstance(item, dict) else str(item)
            if headline:
                section += f"  - {headline}\n"
                count += 1
                
        if count == 0:
            return "RECENT NEWS:\n  - No recent news available"
            
        return section.rstrip()
    except Exception as e:
        logger.error(f"Error formatting news section: {e}")
        return "RECENT NEWS:\n  - No recent news available"

def format_calendar_section(calendar_data):
    """
    Format upcoming events section.
    
    Args:
        calendar_data (dict): Calendar data dictionary.
        
    Returns:
        str: Formatted calendar section string.
    """
    try:
        if not isinstance(calendar_data, dict):
            return 'UPCOMING HIGH IMPACT EVENTS: "None in the next 4 hours"'
            
        events = calendar_data.get("events_today", [])
        if not events:
            return 'UPCOMING HIGH IMPACT EVENTS: "None in the next 4 hours"'
            
        events_str = ", ".join([str(e) for e in events])
        return f"UPCOMING HIGH IMPACT EVENTS: {events_str}"
    except Exception as e:
        logger.error(f"Error formatting calendar section: {e}")
        return 'UPCOMING HIGH IMPACT EVENTS: "None in the next 4 hours"'

def build_prompt(ensemble_signal, market_snapshot):
    """
    Build complete prompt from signal and snapshot.
    
    Args:
        ensemble_signal (dict): The ensemble signal dictionary.
        market_snapshot (dict): The market snapshot dictionary.
        
    Returns:
        str: The complete prompt string.
    """
    try:
        if not validate_inputs(ensemble_signal, market_snapshot):
            logger.error("Invalid inputs to build_prompt")
            return ""
            
        price = market_snapshot["price"]["latest_candle"]["close"]
        dxy_bias = market_snapshot["dxy"]["trend"]
        
        signal_part = format_signal_section(ensemble_signal)
        header = (
            "You are a professional gold (XAU/USD) trading analyst.\n"
            "Analyze this trade signal and decide if it is safe to take.\n\n"
            f"{signal_part}\n"
            f"ENTRY PRICE: {price:.2f}\n"
            f"DXY BIAS: {dxy_bias}"
        )
        
        model_sec = format_model_section(ensemble_signal)
        news_sec = format_news_section(market_snapshot.get("news", []))
        cal_sec = format_calendar_section(market_snapshot.get("calendar", {}))
        
        rules_sec = (
            "RULES:\n"
            "  - Reply YES if the signal aligns with current news and context\n"
            "  - Reply NO if news contradicts the signal direction\n"
            "  - Reply NO if a HIGH impact event occurs within the next 15 minutes\n"
            "  - Reply NO if DXY bias strongly contradicts the signal\n"
            "  - Your entire response must be ONLY one of these two formats:\n"
            "      YES: one sentence explaining why\n"
            "      NO: one sentence explaining why\n"
            "  - No preamble. No extra text. No markdown."
        )
        
        prompt = f"{header}\n\n{model_sec}\n\n{news_sec}\n\n{cal_sec}\n\n{rules_sec}"
        return prompt
        
    except Exception as e:
        logger.error(f"Unexpected error in build_prompt: {e}")
        return ""
