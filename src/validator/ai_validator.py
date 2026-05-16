"""
AI Validator Module

The core validation engine. Connects to Ollama, sends the prompt built by prompt_builder.py,
receives the raw LLM response, parses it into a clean YES or NO decision, logs the full decision
with context, and returns a structured result dictionary to Layer 4.
"""

import logging
import logging.handlers
import os
import re
import time
import sqlite3
import threading
from datetime import datetime
import ollama

from config import settings
from src.validator.prompt_builder import build_prompt

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.handlers.RotatingFileHandler(
    getattr(settings, "VALIDATOR_LOG_FILE", "logs/validator.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=3
)
file_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(file_handler)

def check_ollama_connection():
    """
    Verify Ollama is running and model is available.
    """
    try:
        models_info = ollama.list()
        models = models_info.get("models", [])
        expected_model = getattr(settings, "OLLAMA_MODEL", "qwen3:8b")
        for m in models:
            if m.get("name") == expected_model or m.get("model") == expected_model:
                return True
        logger.critical("Model not found")
        return False
    except Exception as e:
        logger.critical(f"Ollama not available: {e}")
        return False

def send_prompt(prompt):
    """
    Send prompt to Qwen3:8b and get raw response.
    Wraps ollama.chat in a thread to handle timeouts.
    """
    if not prompt:
        return None
        
    result = {"response": None, "error": None}
    
    def target():
        try:
            resp = ollama.chat(
                model=getattr(settings, "OLLAMA_MODEL", "qwen3:8b"),
                messages=[{"role": "user", "content": prompt}]
            )
            result["response"] = resp.get("message", {}).get("content")
        except Exception as e:
            result["error"] = e
            
    max_retries = getattr(settings, "OLLAMA_MAX_RETRIES", 1)
    timeout = getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 30)
    
    for attempt in range(max_retries + 1):
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            logger.error(f"Ollama request timed out on attempt {attempt + 1}")
            continue
            
        if result["error"]:
            logger.error(f"Ollama request error: {result['error']}")
            continue
            
        if result["response"] is not None:
            return result["response"]
            
    return None

def parse_response(raw_response):
    """
    Extract YES/NO and reason from raw response.
    """
    if not raw_response:
        return {"decision": "NO", "validated": False, "reason": "Empty response"}
        
    # Step 1: Remove think tags and their content
    cleaned = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
    
    # Step 2: Find YES or NO line
    response_upper = cleaned.upper()
    
    if response_upper.startswith("YES"):
        decision = "YES"
        validated = True
        reason = cleaned[4:].strip()
            
    elif response_upper.startswith("NO"):
        decision = "NO"
        validated = False
        reason = cleaned[3:].strip()
            
    else:
        # Search for YES/NO anywhere in cleaned response
        if "YES" in response_upper:
            decision = "YES"
            validated = True
            reason = "Extracted from response"
        elif "NO" in response_upper:
            decision = "NO"
            validated = False
            reason = "Extracted from response"
        else:
            decision = "NO"
            validated = False
            reason = "LLM response could not be parsed — defaulting to NO"
            
    return {"decision": decision, "validated": validated, "reason": reason}

def log_decision(validation_result):
    """
    Log full decision to file and SQLite.
    """
    try:
        # 1. Log to file
        log_line = (f"[{validation_result['timestamp']}] SIGNAL={validation_result['signal']} | "
                    f"DECISION={validation_result['decision']} | SCORE={validation_result.get('score', 0.0)} | "
                    f"LATENCY={validation_result['latency_ms']}ms | REASON={validation_result['reason']}")
        logger.info(log_line)
        
        # 2. Log to SQLite
        db_path = "data/validator.db"
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validator_decisions (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    signal    TEXT NOT NULL,
                    decision  TEXT NOT NULL,
                    reason    TEXT,
                    score     REAL,
                    latency   INTEGER,
                    model     TEXT
                )
            ''')
            cursor.execute('''
                INSERT INTO validator_decisions 
                (timestamp, signal, decision, reason, score, latency, model)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                validation_result['timestamp'],
                validation_result['signal'],
                validation_result['decision'],
                validation_result['reason'],
                validation_result.get('score', 0.0),
                validation_result['latency_ms'],
                validation_result['model']
            ))
            conn.commit()
            
    except Exception as e:
        logger.error(f"Error logging decision: {e}")

def get_default_no(reason):
    """
    Return a standard NO result for error cases.
    """
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signal": "UNKNOWN",
        "validated": False,
        "decision": "NO",
        "reason": reason,
        "raw_response": None,
        "model": getattr(settings, "OLLAMA_MODEL", "qwen3:8b"),
        "latency_ms": 0,
        "passed_to_risk": False
    }

def validate(ensemble_signal, market_snapshot):
    """
    Full validation pipeline.
    """
    try:
        start_time = time.time()
        
        if not check_ollama_connection():
            return get_default_no("Ollama not available")
            
        prompt = build_prompt(ensemble_signal, market_snapshot)
        if not prompt:
            logger.error("Empty prompt from builder")
            return get_default_no("Empty prompt")
            
        raw_response = send_prompt(prompt)
        if not raw_response:
            return get_default_no("Response timeout")
            
        parsed = parse_response(raw_response)
        
        if parsed["reason"] == "LLM response could not be parsed — defaulting to NO":
            logger.warning("Parse error")
        
        latency = int((time.time() - start_time) * 1000)
        
        signal = ensemble_signal.get("final_signal", "UNKNOWN")
        timestamp = ensemble_signal.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        score = ensemble_signal.get("weighted_score", 0.0)
        
        result = {
            "timestamp": timestamp,
            "signal": signal,
            "validated": parsed["validated"],
            "decision": parsed["decision"],
            "reason": parsed["reason"],
            "raw_response": raw_response,
            "model": getattr(settings, "OLLAMA_MODEL", "qwen3:8b"),
            "latency_ms": latency,
            "passed_to_risk": parsed["validated"],
            "score": score
        }
        
        log_decision(result)
        return result
        
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        return get_default_no("Unexpected error")
