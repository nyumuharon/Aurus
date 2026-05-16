"""
Test AI Validator Module

Stage 2 tests for the AI validator.
"""

import pytest
import sqlite3
import os
import time
from unittest.mock import patch, MagicMock
import src.validator.ai_validator as ai_val
from src.validator.ai_validator import (
    check_ollama_connection,
    send_prompt,
    parse_response,
    validate,
    log_decision,
    get_default_no
)

@pytest.fixture
def mock_ollama_list():
    with patch('src.validator.ai_validator.ollama.list') as mock_list:
        yield mock_list

@pytest.fixture
def mock_ollama_chat():
    with patch('src.validator.ai_validator.ollama.chat') as mock_chat:
        yield mock_chat

def test_check_ollama_connection_returns_true_when_ollama_is_running(mock_ollama_list):
    mock_ollama_list.return_value = {"models": [{"name": "qwen3:8b"}]}
    assert check_ollama_connection() is True

def test_check_ollama_connection_returns_false_when_ollama_is_not_running(mock_ollama_list):
    mock_ollama_list.side_effect = Exception("Connection error")
    assert check_ollama_connection() is False

def test_send_prompt_returns_non_empty_string_for_valid_prompt(mock_ollama_chat):
    mock_ollama_chat.return_value = {"message": {"content": "YES: Good setup"}}
    response = send_prompt("Test prompt")
    assert isinstance(response, str)
    assert response == "YES: Good setup"

def test_send_prompt_returns_none_on_timeout():
    with patch('src.validator.ai_validator.ollama.chat') as mock_chat:
        def slow_chat(*args, **kwargs):
            time.sleep(1)
        mock_chat.side_effect = slow_chat
        
        old_timeout = getattr(ai_val.settings, "OLLAMA_TIMEOUT_SECONDS", 30)
        old_retries = getattr(ai_val.settings, "OLLAMA_MAX_RETRIES", 1)
        
        ai_val.settings.OLLAMA_TIMEOUT_SECONDS = 0.1
        ai_val.settings.OLLAMA_MAX_RETRIES = 0
        
        try:
            response = send_prompt("Test prompt")
            assert response is None
        finally:
            ai_val.settings.OLLAMA_TIMEOUT_SECONDS = old_timeout
            ai_val.settings.OLLAMA_MAX_RETRIES = old_retries

def test_parse_response_returns_yes_decision_for_yes_reason_input():
    res = parse_response("YES: Looks good")
    assert res["decision"] == "YES"
    assert res["validated"] is True

def test_parse_response_returns_no_decision_for_no_reason_input():
    res = parse_response("NO: Bad setup")
    assert res["decision"] == "NO"
    assert res["validated"] is False

def test_parse_response_returns_no_decision_for_unparseable_input():
    res = parse_response("Maybe we should buy")
    assert res["decision"] == "NO"
    assert res["validated"] is False

def test_parse_response_strips_think_tags_before_parsing():
    raw = "<think>\nBlah blah\n</think>\nYES: Clear buy"
    res = parse_response(raw)
    assert res["decision"] == "YES"
    assert res["validated"] is True

def test_parse_response_extracts_reason_correctly_from_yes_response():
    res = parse_response("YES: Clear buy signal")
    assert res["reason"] == "Clear buy signal"

def test_parse_response_extracts_reason_correctly_from_no_response():
    res = parse_response("NO: Clear sell signal")
    assert res["reason"] == "Clear sell signal"

def test_validate_returns_dict_with_all_required_keys(mock_ollama_list, mock_ollama_chat):
    mock_ollama_list.return_value = {"models": [{"name": "qwen3:8b"}]}
    mock_ollama_chat.return_value = {"message": {"content": "YES: Good"}}
    
    signal = {"final_signal": "BUY", "weighted_score": 0.9, "individual_signals": {}}
    snapshot = {"price": {"latest_candle": {"close": 1.0}}, "news": [], "dxy": {"trend": "NEUTRAL"}, "calendar": {}}
    
    with patch('src.validator.ai_validator.log_decision'):
        res = validate(signal, snapshot)
    
    required_keys = ["timestamp", "signal", "validated", "decision", "reason", "raw_response", "model", "latency_ms", "passed_to_risk"]
    for key in required_keys:
        assert key in res

def test_validate_returns_validated_true_for_clear_buy_signal(mock_ollama_list, mock_ollama_chat):
    mock_ollama_list.return_value = {"models": [{"name": "qwen3:8b"}]}
    mock_ollama_chat.return_value = {"message": {"content": "YES: Good setup"}}
    
    signal = {"final_signal": "BUY", "weighted_score": 0.9, "individual_signals": {}}
    snapshot = {"price": {"latest_candle": {"close": 1.0}}, "news": [], "dxy": {"trend": "NEUTRAL"}, "calendar": {}}
    
    with patch('src.validator.ai_validator.log_decision'):
        res = validate(signal, snapshot)
        
    assert res["validated"] is True

def test_validate_returns_validated_false_when_ollama_is_down(mock_ollama_list):
    mock_ollama_list.side_effect = Exception("Down")
    
    signal = {"final_signal": "BUY", "weighted_score": 0.9, "individual_signals": {}}
    snapshot = {"price": {"latest_candle": {"close": 1.0}}, "news": [], "dxy": {"trend": "NEUTRAL"}, "calendar": {}}
    
    res = validate(signal, snapshot)
    assert res["validated"] is False

def test_validate_returns_validated_false_when_prompt_is_empty():
    res = validate(None, None)
    assert res["validated"] is False

def test_get_default_no_returns_correct_structure():
    res = get_default_no("Test reason")
    assert res["validated"] is False
    assert res["decision"] == "NO"
    assert res["reason"] == "Test reason"
    assert res["passed_to_risk"] is False

def test_log_decision_writes_to_log_file_without_error():
    res = get_default_no("Test reason")
    res["score"] = 0.5
    try:
        log_decision(res)
    except Exception as e:
        pytest.fail(f"log_decision raised Exception: {e}")

def test_log_decision_writes_to_sqlite_without_error():
    db_path = "data/validator.db"
    
    res = get_default_no("Test reason")
    res["score"] = 0.5
    
    log_decision(res)
    
    assert os.path.exists(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM validator_decisions")
        rows = cursor.fetchall()
        assert len(rows) > 0
