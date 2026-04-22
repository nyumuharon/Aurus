"""Market-closure aware gap classification for XAU/USD research data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from aurus.data.quality import MissingBarGap

ANNUAL_XAUUSD_CLOSURE_MONTH_DAYS = frozenset(
    {
        (1, 1),  # New Year's Day
        (7, 4),  # U.S. Independence Day
        (12, 25),  # Christmas Day
    }
)
XAUUSD_BROKER_OBSERVED_CLOSURE_DATES = frozenset(
    {
        date(2025, 7, 3),
    }
)


@dataclass(frozen=True)
class GapPolicyReport:
    """Summary of expected and unexpected timestamp gaps."""

    expected_closure_gaps: int
    unexpected_gaps: int
    expected_missing_bars: int
    unexpected_missing_bars: int

    @property
    def has_unexpected_gaps(self) -> bool:
        """Return True when data has gaps outside the coarse market-closure policy."""

        return self.unexpected_gaps > 0


def classify_xauusd_gaps(gaps: tuple[MissingBarGap, ...]) -> GapPolicyReport:
    """Classify gaps using a coarse XAU/USD weekday/weekend market-closure policy."""

    expected_gaps = 0
    unexpected_gaps = 0
    expected_missing = 0
    unexpected_missing = 0
    for gap in gaps:
        missing_count = len(gap.missing_timestamps)
        if is_expected_xauusd_closure(gap):
            expected_gaps += 1
            expected_missing += missing_count
        else:
            unexpected_gaps += 1
            unexpected_missing += missing_count

    return GapPolicyReport(
        expected_closure_gaps=expected_gaps,
        unexpected_gaps=unexpected_gaps,
        expected_missing_bars=expected_missing,
        unexpected_missing_bars=unexpected_missing,
    )


def is_expected_xauusd_closure(gap: MissingBarGap) -> bool:
    """Return True for coarse weekend/holiday closures in spot-gold style data."""

    if not gap.missing_timestamps:
        return False
    timestamps = (gap.previous_timestamp, *gap.missing_timestamps, gap.next_timestamp)
    return (
        any(_is_weekend(timestamp) for timestamp in timestamps)
        or _spans_weekend(gap.previous_timestamp, gap.next_timestamp)
        or any(_is_annual_market_holiday(timestamp.date()) for timestamp in timestamps)
        or any(_is_broker_observed_closure(timestamp.date()) for timestamp in timestamps)
    )


def _is_weekend(timestamp: datetime) -> bool:
    return timestamp.weekday() in {5, 6}


def _spans_weekend(start: datetime, end: datetime) -> bool:
    current_day = start.date()
    end_day = end.date()
    while current_day <= end_day:
        if current_day.weekday() in {5, 6}:
            return True
        current_day = current_day.fromordinal(current_day.toordinal() + 1)
    return False


def _is_annual_market_holiday(day: date) -> bool:
    return (day.month, day.day) in ANNUAL_XAUUSD_CLOSURE_MONTH_DAYS


def _is_broker_observed_closure(day: date) -> bool:
    return day in XAUUSD_BROKER_OBSERVED_CLOSURE_DATES
