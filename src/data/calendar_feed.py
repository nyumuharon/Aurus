# src/data/calendar_feed.py
"""Aurus Sprint 1 — Stage 4: Economic Calendar Feed
====================================================
Fetches today's high-impact economic events from the Forex Factory public
calendar JSON feed. Used to avoid opening new trades during high-impact
news releases — a critical prop firm survival rule.

Rules:
- All errors are logged via the Python logging module — never use print().
- Calendar failure must never block other feeds — treat as no upcoming events.
- is_high_impact_window() always returns False (safe) when data is unavailable.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Calendar API — Forex Factory public JSON feed (no key required)
# ---------------------------------------------------------------------------
_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_REQUEST_TIMEOUT = 10       # seconds
_RETRY_DELAY = 5            # seconds — single retry on failure

# ---------------------------------------------------------------------------
# Filtering constants (per build plan)
# ---------------------------------------------------------------------------
_VALID_CURRENCIES = {"USD", "XAU"}
_VALID_IMPACTS = {"High", "Medium"}        # Forex Factory uses Title-case
_HIGH_IMPACT_WINDOW_MINUTES = 15           # ±15 min around a HIGH event


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_datetime(raw: str):
    """Parse a Forex Factory ISO-8601 datetime string into a UTC datetime.

    Forex Factory returns timestamps like ``2026-03-01T14:30:00-05:00``
    (US/Eastern). We convert to UTC for consistent time comparisons.

    Args:
        raw: ISO-8601 datetime string from the Forex Factory feed.

    Returns:
        datetime (UTC, timezone-aware) or None if parsing fails.
    """
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to parse datetime '%s': %s", raw, exc)
        return None


def _fetch_raw_events():
    """Fetch the raw event list from the Forex Factory calendar API.

    Retries once after _RETRY_DELAY seconds on any request failure.

    Returns:
        list[dict] — raw event dicts from the API.
        None       — request failed after both attempts.
    """
    for attempt in range(1, 3):
        try:
            response = requests.get(_CALENDAR_URL, timeout=_REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error(
                "Calendar API request failed (attempt %d/2): %s", attempt, exc
            )
            if attempt == 1:
                logger.info("Retrying calendar API in %d seconds…", _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)

    logger.error("All calendar API retries failed.")
    return None


def _to_standard_event(raw: dict):
    """Convert a raw FF event dict to the Aurus standard format.

    Applies currency and impact filters. Returns None if the event does
    not pass both filters (currency in USD/XAU AND impact in High/Medium).

    Args:
        raw: Single raw event dict from the Forex Factory feed.

    Returns:
        dict with keys (timestamp, event, impact, currency), or None.
    """
    currency = (raw.get("country") or raw.get("currency") or "").upper().strip()
    impact_raw = (raw.get("impact") or "").strip()
    impact = impact_raw[0].upper() + impact_raw[1:].lower() if impact_raw else ""

    if currency not in _VALID_CURRENCIES:
        return None
    if impact not in _VALID_IMPACTS:
        return None

    raw_dt = raw.get("date") or raw.get("datetime") or ""
    dt = _parse_datetime(raw_dt)
    if dt is None:
        return None

    return {
        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "event": raw.get("title") or raw.get("name") or "Unknown",
        "impact": impact.upper(),      # store as HIGH | MEDIUM
        "currency": currency,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_todays_events() -> list:
    """Fetch all high and medium impact USD/XAU economic events for today.

    Contacts the Forex Factory calendar API, filters to today's UTC date,
    and removes LOW impact and non-USD/XAU currency events.

    Returns:
        list[dict] — events with keys: timestamp, event, impact, currency.
        []         — no matching events, API returned zero data, or API down.
    """
    raw_events = _fetch_raw_events()
    if raw_events is None:
        logger.warning("Calendar API unavailable — returning empty event list.")
        return []

    if not raw_events:
        logger.warning("Calendar API returned zero events.")
        return []

    today_utc = datetime.now(tz=timezone.utc).date()
    result = []

    for raw in raw_events:
        event = _to_standard_event(raw)
        if event is None:
            continue
        try:
            event_date = datetime.strptime(
                event["timestamp"], "%Y-%m-%d %H:%M:%S"
            ).date()
        except ValueError:
            continue
        if event_date == today_utc:
            result.append(event)

    logger.info("Calendar: %d high/medium USD/XAU events today.", len(result))
    return result


def is_high_impact_window(events: list = None) -> bool:
    """Check whether current UTC time is within 15 minutes of a HIGH event.

    Fetches today's events if none are provided. Returns False (safe) if
    event data is unavailable — never blocks the trading system.

    Args:
        events: Optional pre-fetched event list. Fetches fresh if None.

    Returns:
        True  — within ±15 minutes of a HIGH impact event.
        False — outside window, no events, or data unavailable.
    """
    try:
        if events is None:
            events = get_todays_events()
        if not events:
            return False

        now = datetime.now(tz=timezone.utc)
        window = timedelta(minutes=_HIGH_IMPACT_WINDOW_MINUTES)

        for event in events:
            if event.get("impact") != "HIGH":
                continue
            try:
                event_dt = datetime.strptime(
                    event["timestamp"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if abs(now - event_dt) <= window:
                logger.warning(
                    "HIGH impact window active: '%s' at %s",
                    event["event"], event["timestamp"],
                )
                return True

        return False

    except Exception as exc:
        logger.error("is_high_impact_window() error — defaulting to False: %s", exc)
        return False


def get_next_event(events: list = None):
    """Return the next upcoming economic event after the current UTC time.

    Searches today's filtered event list for the earliest event that has
    not yet occurred. Returns None if no future events exist.

    Args:
        events: Optional pre-fetched event list. Fetches fresh if None.

    Returns:
        dict — next upcoming event in standard format, or None.
    """
    try:
        if events is None:
            events = get_todays_events()
        if not events:
            return None

        now = datetime.now(tz=timezone.utc)
        upcoming = []

        for event in events:
            try:
                event_dt = datetime.strptime(
                    event["timestamp"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if event_dt > now:
                upcoming.append((event_dt, event))

        if not upcoming:
            logger.info("No upcoming events found for today.")
            return None

        upcoming.sort(key=lambda x: x[0])
        return upcoming[0][1]

    except Exception as exc:
        logger.error("get_next_event() error: %s", exc)
        return None
