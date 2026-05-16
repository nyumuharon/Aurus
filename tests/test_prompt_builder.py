"""
Test Prompt Builder Module

Stage 1 tests for the AI validator prompt builder.
"""

import pytest
from src.validator.prompt_builder import (
    build_prompt,
    validate_inputs,
    format_news_section,
    format_calendar_section
)

@pytest.fixture
def valid_ensemble_signal():
    return {
        "timestamp": "2026-03-01 10:00:00",
        "final_signal": "BUY",
        "weighted_score": 0.73,
        "individual_signals": {
            "lstm":          {"signal": "BUY",     "confidence": 0.82},
            "tft":           {"signal": "BULLISH", "confidence": 0.74},
            "random_forest": {"signal": "BUY",     "confidence": 0.65},
            "smc_detector":  {"signal": "BUY",     "confidence": 0.75}
        }
    }

@pytest.fixture
def valid_market_snapshot():
    return {
        "price": {
            "latest_candle": {"close": 2988.75}
        },
        "news": [
            {"headline": "Fed remains dovish on rates", "sentiment": "bullish"},
            {"headline": "Gold demand rises in Asia", "sentiment": "bullish"}
        ],
        "dxy": {"trend": "BEARISH", "price": 104.32},
        "calendar": {
            "events_today": ["NFP at 8:30 AM"],
            "high_impact_window": False
        }
    }

def test_build_prompt_returns_non_empty_string_with_valid_inputs(valid_ensemble_signal, valid_market_snapshot):
    prompt = build_prompt(valid_ensemble_signal, valid_market_snapshot)
    assert isinstance(prompt, str)
    assert len(prompt) > 0

def test_returned_prompt_contains_signal_direction(valid_ensemble_signal, valid_market_snapshot):
    prompt = build_prompt(valid_ensemble_signal, valid_market_snapshot)
    assert "SIGNAL: BUY" in prompt

def test_returned_prompt_contains_confidence_score(valid_ensemble_signal, valid_market_snapshot):
    prompt = build_prompt(valid_ensemble_signal, valid_market_snapshot)
    assert "CONFIDENCE SCORE: 0.73" in prompt

def test_returned_prompt_contains_dxy_bias(valid_ensemble_signal, valid_market_snapshot):
    prompt = build_prompt(valid_ensemble_signal, valid_market_snapshot)
    assert "DXY BIAS: BEARISH" in prompt

def test_returned_prompt_contains_at_least_one_news_headline(valid_ensemble_signal, valid_market_snapshot):
    prompt = build_prompt(valid_ensemble_signal, valid_market_snapshot)
    assert "Fed remains dovish on rates" in prompt

def test_returned_prompt_contains_rules_section(valid_ensemble_signal, valid_market_snapshot):
    prompt = build_prompt(valid_ensemble_signal, valid_market_snapshot)
    assert "RULES:" in prompt
    assert "Reply YES if the signal aligns with current news" in prompt

def test_validate_inputs_returns_true_for_valid_inputs(valid_ensemble_signal, valid_market_snapshot):
    assert validate_inputs(valid_ensemble_signal, valid_market_snapshot) is True

def test_validate_inputs_returns_false_when_ensemble_signal_is_none(valid_market_snapshot):
    assert validate_inputs(None, valid_market_snapshot) is False

def test_validate_inputs_returns_false_when_market_snapshot_is_none(valid_ensemble_signal):
    assert validate_inputs(valid_ensemble_signal, None) is False

def test_build_prompt_returns_empty_string_when_inputs_are_invalid(valid_market_snapshot):
    prompt = build_prompt(None, valid_market_snapshot)
    assert prompt == ""

def test_format_news_section_handles_empty_news_list_gracefully():
    prompt = format_news_section([])
    assert "No recent news available" in prompt

def test_format_calendar_section_handles_empty_events_gracefully():
    prompt = format_calendar_section({"events_today": []})
    assert "None in the next 4 hours" in prompt
