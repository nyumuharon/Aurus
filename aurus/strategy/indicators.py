"""Deterministic technical indicators for baseline strategies."""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

from aurus.common.schemas import BarEvent


def ema(values: list[Decimal], period: int) -> list[Decimal]:
    """Calculate an exponential moving average series."""

    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []

    smoothing = Decimal("2") / Decimal(period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value * smoothing) + (result[-1] * (Decimal("1") - smoothing)))
    return result


def true_ranges(bars: list[BarEvent]) -> list[Decimal]:
    """Calculate true range values for a bar sequence."""

    if not bars:
        return []

    ranges = [bars[0].high - bars[0].low]
    for previous, current in pairwise(bars):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return ranges


def atr(bars: list[BarEvent], period: int) -> list[Decimal]:
    """Calculate simple rolling ATR values.

    Values before a full window is available are averaged over available data.
    """

    if period <= 0:
        raise ValueError("period must be positive")

    ranges = true_ranges(bars)
    result: list[Decimal] = []
    for index in range(len(ranges)):
        start = max(0, index + 1 - period)
        window = ranges[start : index + 1]
        result.append(sum(window, Decimal("0")) / Decimal(len(window)))
    return result
