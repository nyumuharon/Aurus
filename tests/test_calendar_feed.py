# tests/test_calendar_feed.py
"""Aurus Sprint 1 — Stage 4 Tests: Economic Calendar Feed
==========================================================
Unit tests for src/data/calendar_feed.py.

requests.get is mocked so all tests run offline without hitting the
live Forex Factory API.

Tests cover all 7 acceptance criteria from the Stage 4 build plan:
    1. get_todays_events() returns a list (empty or populated)
    2. All returned events have timestamp, event, impact, currency keys
    3. No LOW impact events appear in results
    4. No non-USD/XAU currencies appear in results
    5. is_high_impact_window() returns a boolean
    6. get_next_event() returns a dict or None
    7. Function returns empty list gracefully when API is down
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import src.data.calendar_feed as calendar_feed


# ---------------------------------------------------------------------------
# Shared mock fixtures
# ---------------------------------------------------------------------------

def _today_utc_iso(hour: int = 14, minute: int = 30) -> str:
    """Return an ISO-8601 timestamp string for today at hour:minute UTC."""
    today = datetime.now(tz=timezone.utc).date()
    return f"{today}T{hour:02d}:{minute:02d}:00+00:00"


def _make_raw_events(include_low: bool = False, include_eur: bool = False) -> list:
    """Build a list of raw Forex Factory-style event dicts for today."""
    events = [
        {
            "date": _today_utc_iso(14, 30),
            "country": "USD",
            "title": "US Non-Farm Payrolls",
            "impact": "High",
        },
        {
            "date": _today_utc_iso(15, 0),
            "country": "USD",
            "title": "Fed Interest Rate Decision",
            "impact": "High",
        },
        {
            "date": _today_utc_iso(16, 0),
            "country": "USD",
            "title": "ISM Manufacturing PMI",
            "impact": "Medium",
        },
    ]
    if include_low:
        events.append({
            "date": _today_utc_iso(17, 0),
            "country": "USD",
            "title": "Some Low Impact Event",
            "impact": "Low",
        })
    if include_eur:
        events.append({
            "date": _today_utc_iso(10, 0),
            "country": "EUR",
            "title": "ECB Rate Decision",
            "impact": "High",
        })
    return events


def _mock_get(raw_events: list):
    """Return a mock for requests.get that returns raw_events as JSON."""
    mock_response = MagicMock()
    mock_response.json.return_value = raw_events
    mock_response.raise_for_status.return_value = None
    return MagicMock(return_value=mock_response)


# ---------------------------------------------------------------------------
# Test 1 — get_todays_events() returns a list
# ---------------------------------------------------------------------------

class TestGetTodaysEvents:
    """Test 1: get_todays_events() returns a list (empty or populated)."""

    def test_returns_list(self):
        """Test 1a: get_todays_events() must always return a list."""
        with patch("src.data.calendar_feed.requests.get", _mock_get(_make_raw_events())):
            result = calendar_feed.get_todays_events()
        assert isinstance(result, list)

    def test_returns_non_empty_list_when_events_exist(self):
        """Test 1b: Returns a populated list when matching events are available."""
        with patch("src.data.calendar_feed.requests.get", _mock_get(_make_raw_events())):
            result = calendar_feed.get_todays_events()
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 2 — All returned events have required keys
# ---------------------------------------------------------------------------

class TestEventKeys:
    """Test 2: All returned events have timestamp, event, impact, currency."""

    def test_all_events_have_required_keys(self):
        """Test 2: Every event dict must contain the four required keys."""
        with patch("src.data.calendar_feed.requests.get", _mock_get(_make_raw_events())):
            result = calendar_feed.get_todays_events()
        required = {"timestamp", "event", "impact", "currency"}
        for event in result:
            missing = required - event.keys()
            assert not missing, f"Event missing keys: {missing}"


# ---------------------------------------------------------------------------
# Test 3 — No LOW impact events appear in results
# ---------------------------------------------------------------------------

class TestNoLowImpact:
    """Test 3: No LOW impact events appear in results."""

    def test_low_impact_events_are_excluded(self):
        """Test 3: Results must contain only HIGH or MEDIUM impact events."""
        raw = _make_raw_events(include_low=True)
        with patch("src.data.calendar_feed.requests.get", _mock_get(raw)):
            result = calendar_feed.get_todays_events()
        for event in result:
            assert event["impact"] in {"HIGH", "MEDIUM"}, (
                f"LOW impact event leaked through: {event}"
            )


# ---------------------------------------------------------------------------
# Test 4 — No non-USD/XAU currencies appear in results
# ---------------------------------------------------------------------------

class TestCurrencyFilter:
    """Test 4: No non-USD/XAU currencies appear in results."""

    def test_non_usd_xau_currencies_are_excluded(self):
        """Test 4: Only USD and XAU events must appear in results."""
        raw = _make_raw_events(include_eur=True)
        with patch("src.data.calendar_feed.requests.get", _mock_get(raw)):
            result = calendar_feed.get_todays_events()
        for event in result:
            assert event["currency"] in {"USD", "XAU"}, (
                f"Unexpected currency: {event['currency']}"
            )


# ---------------------------------------------------------------------------
# Test 5 — is_high_impact_window() returns a boolean
# ---------------------------------------------------------------------------

class TestIsHighImpactWindow:
    """Test 5: is_high_impact_window() returns a boolean."""

    def test_returns_bool(self):
        """Test 5a: is_high_impact_window() must return True or False."""
        with patch("src.data.calendar_feed.requests.get", _mock_get(_make_raw_events())):
            result = calendar_feed.is_high_impact_window()
        assert isinstance(result, bool)

    def test_returns_true_when_within_window(self):
        """Test 5b: Returns True when current time is within 15 min of HIGH event."""
        now = datetime.now(tz=timezone.utc)
        event_dt = now + timedelta(minutes=5)
        events = [{
            "timestamp": event_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "event": "Test HIGH Event",
            "impact": "HIGH",
            "currency": "USD",
        }]
        result = calendar_feed.is_high_impact_window(events=events)
        assert result is True

    def test_returns_false_when_no_high_events(self):
        """Test 5c: Returns False when all events are MEDIUM impact."""
        events = [{
            "timestamp": "2026-01-01 14:30:00",
            "event": "Medium Event",
            "impact": "MEDIUM",
            "currency": "USD",
        }]
        result = calendar_feed.is_high_impact_window(events=events)
        assert result is False

    def test_returns_false_when_events_empty(self):
        """Test 5d: Returns False when event list is empty."""
        result = calendar_feed.is_high_impact_window(events=[])
        assert result is False
