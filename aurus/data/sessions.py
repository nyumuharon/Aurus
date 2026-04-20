"""Session tagging utilities for UTC market data timestamps."""

from __future__ import annotations

from datetime import UTC, datetime, time
from enum import StrEnum


class TradingSession(StrEnum):
    """Coarse global trading session tags."""

    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"
    ROLLOVER = "rollover"


def normalize_to_utc(timestamp: datetime) -> datetime:
    """Return a timezone-aware timestamp normalized to UTC."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp.astimezone(UTC)


def tag_session(timestamp: datetime) -> TradingSession:
    """Tag a UTC-normalized timestamp with a broad FX metals session.

    Boundaries are intentionally simple UTC clock windows:
    rollover 21:00-22:00, Asia 22:00-07:00, London 07:00-13:00,
    New York 13:00-21:00.
    """

    utc_timestamp = normalize_to_utc(timestamp)
    utc_time = utc_timestamp.time()

    if time(21, 0) <= utc_time < time(22, 0):
        return TradingSession.ROLLOVER
    if utc_time >= time(22, 0) or utc_time < time(7, 0):
        return TradingSession.ASIA
    if time(7, 0) <= utc_time < time(13, 0):
        return TradingSession.LONDON
    return TradingSession.NEW_YORK

