"""Backtest strategy and risk interfaces."""

from __future__ import annotations

from typing import Protocol

from aurus.common.schemas import BarEvent, RiskDecision, SignalEvent


class StrategyCallback(Protocol):
    """Pure strategy callback invoked with replayed bars only."""

    def __call__(self, bars: tuple[BarEvent, ...]) -> list[SignalEvent]:
        """Inspect bars replayed so far and return zero or more signals."""


class RiskEngine(Protocol):
    """Risk decision interface used before simulated execution."""

    def evaluate(self, signal: SignalEvent, bar: BarEvent) -> RiskDecision:
        """Approve, reject, or reduce a signal before execution."""

