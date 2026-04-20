"""Market data quality checks for deterministic research inputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

from aurus.common.schemas import BarEvent

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MissingBarGap:
    """A missing contiguous interval between two observed bar timestamps."""

    previous_timestamp: datetime
    next_timestamp: datetime
    missing_timestamps: tuple[datetime, ...]


def find_duplicate_timestamps(bars: list[BarEvent]) -> tuple[datetime, ...]:
    """Return duplicated bar timestamps in first-observed order."""

    seen: set[datetime] = set()
    duplicates: list[datetime] = []
    duplicate_set: set[datetime] = set()

    for bar in bars:
        if bar.timestamp in seen and bar.timestamp not in duplicate_set:
            duplicates.append(bar.timestamp)
            duplicate_set.add(bar.timestamp)
        seen.add(bar.timestamp)

    return tuple(duplicates)


def reject_duplicate_timestamps(bars: list[BarEvent]) -> None:
    """Raise when duplicate bar timestamps are present."""

    duplicates = find_duplicate_timestamps(bars)
    if not duplicates:
        return

    LOGGER.warning(
        "duplicate bar timestamps detected",
        extra={
            "event": "data_quality.duplicate_timestamps",
            "duplicate_count": len(duplicates),
            "timestamps": [timestamp.isoformat() for timestamp in duplicates],
        },
    )
    duplicate_list = ", ".join(timestamp.isoformat() for timestamp in duplicates)
    raise ValueError(f"duplicate bar timestamps detected: {duplicate_list}")


def find_missing_bars(
    bars: list[BarEvent],
    expected_interval: timedelta,
) -> tuple[MissingBarGap, ...]:
    """Find missing timestamps between sorted bar observations."""

    if expected_interval <= timedelta(0):
        raise ValueError("expected_interval must be positive")
    if len(bars) < 2:
        return ()

    sorted_bars = sorted(bars, key=lambda bar: bar.timestamp)
    gaps: list[MissingBarGap] = []

    for previous_bar, next_bar in pairwise(sorted_bars):
        expected_timestamp = previous_bar.timestamp + expected_interval
        if expected_timestamp >= next_bar.timestamp:
            continue

        missing: list[datetime] = []
        while expected_timestamp < next_bar.timestamp:
            missing.append(expected_timestamp)
            expected_timestamp += expected_interval

        gaps.append(
            MissingBarGap(
                previous_timestamp=previous_bar.timestamp,
                next_timestamp=next_bar.timestamp,
                missing_timestamps=tuple(missing),
            )
        )

    if gaps:
        LOGGER.warning(
            "missing bars detected",
            extra={
                "event": "data_quality.missing_bars",
                "gap_count": len(gaps),
                "missing_count": sum(len(gap.missing_timestamps) for gap in gaps),
            },
        )

    return tuple(gaps)
