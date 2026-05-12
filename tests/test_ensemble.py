"""
Tests for Stage 6 Ensemble Voting Engine Module
===============================================
"""

import pytest
from src.models import ensemble
from config import settings


@pytest.fixture(autouse=True)
def fast_mock_models(monkeypatch):
    """Ensure underlying model signals return instantly with clean test data."""
    dummy_sig = {"signal": "BUY", "confidence": 0.80}
    
    # Safely mock model modules if importable
    try:
        from src.models import lstm_model, tft_model, random_forest, smc_detector
        monkeypatch.setattr(lstm_model, "get_signal", lambda: dummy_sig)
        monkeypatch.setattr(tft_model, "get_signal", lambda: dummy_sig)
        monkeypatch.setattr(random_forest, "get_signal", lambda: dummy_sig)
        monkeypatch.setattr(smc_detector, "get_signal", lambda: dummy_sig)
    except Exception:
        pass


def test_collect_signals_keys():
    """1. collect_signals() returns dict with all 4 model keys"""
    signals = ensemble.collect_signals()
    assert isinstance(signals, dict)
    for k in ["lstm", "tft", "random_forest", "smc_detector"]:
        assert k in signals


def test_calculate_weighted_score_known():
    """2. calculate_weighted_score() returns correct value for known inputs"""
    # Create explicit mock signals dict where all models vote BUY with 1.0 confidence
    sigs = {
        "lstm": {"signal": "BUY", "confidence": 1.0},
        "tft": {"signal": "BULLISH", "confidence": 1.0},
        "random_forest": {"signal": "BUY", "confidence": 1.0},
        "smc_detector": {"signal": "BUY", "confidence": 1.0}
    }
    score = ensemble.calculate_weighted_score(sigs)
    # Expected: 1.0 * 0.3 + 1.0 * 0.3 + 1.0 * 0.2 + 1.0 * 0.2 = 1.0
    assert abs(score - 1.0) < 1e-4


def test_determine_signal_buy():
    """3. weighted_score of 0.73 → BUY signal"""
    settings.ENSEMBLE_THRESHOLD = 0.60
    sig = ensemble.determine_signal(0.73)
    assert sig == "BUY"


def test_determine_signal_sell():
    """4. weighted_score of -0.73 → SELL signal"""
    settings.ENSEMBLE_THRESHOLD = 0.60
    sig = ensemble.determine_signal(-0.73)
    assert sig == "SELL"


def test_determine_signal_no_trade():
    """5. weighted_score of 0.30 → NO_TRADE signal"""
    settings.ENSEMBLE_THRESHOLD = 0.60
    sig = ensemble.determine_signal(0.30)
    assert sig == "NO_TRADE"


def test_get_ensemble_signal_structure():
    """6. get_ensemble_signal() returns dict with all required keys"""
    res = ensemble.get_ensemble_signal()
    assert isinstance(res, dict)
    for k in ["timestamp", "final_signal", "weighted_score", "threshold", "individual_signals", "passed_to_validator"]:
        assert k in res


def test_final_signal_values():
    """7. final_signal is one of BUY, SELL, or NO_TRADE"""
    res = ensemble.get_ensemble_signal()
    assert res["final_signal"] in {"BUY", "SELL", "NO_TRADE"}


def test_passed_to_validator_logic():
    """8. passed_to_validator is True only when score >= threshold"""
    # Directly test threshold alignment
    settings.ENSEMBLE_THRESHOLD = 0.60
    res = ensemble.get_ensemble_signal()
    expected = (res["final_signal"] in {"BUY", "SELL"})
    assert res["passed_to_validator"] == expected


def test_graceful_degradation_one_fail():
    """9. System returns NO_TRADE gracefully when one model fails"""
    # Pass custom missing/failing inputs to score calculation
    sigs = {
        "lstm": None,  # Failed
        "tft": {"signal": "HOLD", "confidence": 0.5},
        "random_forest": {"signal": "HOLD", "confidence": 0.5},
        "smc_detector": {"signal": "HOLD", "confidence": 0.5}
    }
    score = ensemble.calculate_weighted_score(sigs)
    sig = ensemble.determine_signal(score)
    assert sig == "NO_TRADE"


def test_all_models_fail():
    """10. System returns NO_TRADE when all models fail"""
    sigs = {
        "lstm": None,
        "tft": None,
        "random_forest": None,
        "smc_detector": None
    }
    score = ensemble.calculate_weighted_score(sigs)
    sig = ensemble.determine_signal(score)
    assert score == 0.0
    assert sig == "NO_TRADE"
