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
