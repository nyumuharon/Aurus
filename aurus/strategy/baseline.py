"""First deterministic XAU/USD baseline strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from aurus.common.schemas import BarEvent, Side, SignalEvent, SourceMetadata
from aurus.data.sessions import TradingSession, tag_session
from aurus.strategy.indicators import atr, ema

LOGGER = logging.getLogger(__name__)
STRATEGY_SOURCE = SourceMetadata(name="baseline-xauusd-v1", kind="strategy")


@dataclass(frozen=True)
class BaselineStrategyConfig:
    """Configurable parameters for the first baseline strategy."""

    instrument: str = "XAU/USD"
    execution_timeframe: str = "5m"
    context_timeframe: str = "1h"
    context_ema_period: int = 50
    execution_ema_period: int = 20
    atr_period: int = 14
    min_atr: Decimal = Decimal("1.0")
    max_spread: Decimal = Decimal("0.50")
    allowed_sessions: frozenset[str] = frozenset(
        {TradingSession.LONDON.value, TradingSession.NEW_YORK.value}
    )
    early_new_york_end_hour_utc: int = 16
    pullback_tolerance: Decimal = Decimal("0")
    atr_stop_floor_multiplier: Decimal = Decimal("1")
    reward_risk: Decimal = Decimal("2")
    strength: Decimal = Decimal("1")
    quantity: Decimal = Decimal("1")


@dataclass(frozen=True)
class StopTarget:
    """Calculated protective stop and fixed-R target."""

    stop_loss: Decimal
    take_profit: Decimal
    risk_per_unit: Decimal


class BaselineXauUsdStrategy:
    """Deterministic 1H trend plus 5M pullback baseline strategy."""

    def __init__(
        self,
        *,
        context_bars: list[BarEvent],
        config: BaselineStrategyConfig | None = None,
    ) -> None:
        self.config = config or BaselineStrategyConfig()
        self.context_bars = sorted(
            [bar for bar in context_bars if self._is_context_bar(bar)],
            key=lambda bar: bar.timestamp,
        )

    def __call__(self, bars: tuple[BarEvent, ...]) -> list[SignalEvent]:
        execution_bars = [bar for bar in bars if self._is_execution_bar(bar)]
        if len(execution_bars) < max(2, self.config.execution_ema_period, self.config.atr_period):
            return []

        current = execution_bars[-1]
        previous = execution_bars[-2]
        blocked_reason = self._blocked_reason(current)
        if blocked_reason is not None:
            self._log_block(current, blocked_reason)
            return []

        context = self._context_until(current)
        if len(context) < self.config.context_ema_period + 1:
            self._log_block(current, "insufficient_context")
            return []

        trend = self._trend(context)
        if trend is None:
            self._log_block(current, "no_context_trend")
            return []

        execution_ema = ema([bar.close for bar in execution_bars], self.config.execution_ema_period)
        current_atr = atr(execution_bars, self.config.atr_period)[-1]
        if current_atr < self.config.min_atr:
            self._log_block(current, "atr_below_threshold", atr=str(current_atr))
            return []

        side = self._entry_side(
            trend=trend,
            previous=previous,
            current=current,
            ema20=execution_ema[-2],
        )
        if side is None:
            return []

        stop_target = calculate_stop_target(
            side=side,
            entry_price=current.close,
            previous_bar=previous,
            confirmation_bar=current,
            atr_value=current_atr,
            atr_floor_multiplier=self.config.atr_stop_floor_multiplier,
            reward_risk=self.config.reward_risk,
        )
        signal = SignalEvent(
            timestamp=current.timestamp,
            correlation_id=f"baseline-{current.correlation_id}",
            source=STRATEGY_SOURCE,
            signal_id=f"baseline-{side.value}-{current.timestamp.isoformat()}",
            strategy_id="baseline-xauusd-v1",
            instrument=current.instrument,
            side=side,
            strength=self.config.strength,
            reason="trend_pullback_confirmation",
            features={
                "context_trend": trend.value,
                "context_ema_period": self.config.context_ema_period,
                "execution_ema_period": self.config.execution_ema_period,
                "atr_period": self.config.atr_period,
                "atr": str(current_atr),
                "ema20": str(execution_ema[-2]),
                "stop_loss": str(stop_target.stop_loss),
                "take_profit": str(stop_target.take_profit),
                "risk_per_unit": str(stop_target.risk_per_unit),
                "reward_risk": str(self.config.reward_risk),
                "quantity": str(self.config.quantity),
            },
        )
        LOGGER.info(
            "baseline signal emitted",
            extra={
                "event": "strategy.signal_emitted",
                "strategy_id": signal.strategy_id,
                "signal_id": signal.signal_id,
                "side": signal.side,
                "timestamp": signal.timestamp.isoformat(),
                "rationale": signal.features,
            },
        )
        return [signal]

    def _is_execution_bar(self, bar: BarEvent) -> bool:
        return (
            bar.instrument == self.config.instrument
            and bar.timeframe == self.config.execution_timeframe
        )

    def _is_context_bar(self, bar: BarEvent) -> bool:
        return (
            bar.instrument == self.config.instrument
            and bar.timeframe == self.config.context_timeframe
        )

    def _blocked_reason(self, bar: BarEvent) -> str | None:
        session = tag_session(bar.timestamp)
        if session.value not in self.config.allowed_sessions:
            return f"blocked_session:{session.value}"
        if (
            session == TradingSession.NEW_YORK
            and bar.timestamp.hour >= self.config.early_new_york_end_hour_utc
        ):
            return "blocked_session:late_new_york"
        if bar.spread is None:
            return "missing_spread"
        if bar.spread > self.config.max_spread:
            return "spread_above_threshold"
        return None

    def _context_until(self, bar: BarEvent) -> list[BarEvent]:
        return [
            context_bar
            for context_bar in self.context_bars
            if context_bar.timestamp <= bar.timestamp
        ]

    def _trend(self, context: list[BarEvent]) -> Side | None:
        closes = [bar.close for bar in context]
        ema_values = ema(closes, self.config.context_ema_period)
        current_close = closes[-1]
        current_ema = ema_values[-1]
        previous_ema = ema_values[-2]
        slope = current_ema - previous_ema

        if current_close > current_ema and slope > Decimal("0"):
            return Side.BUY
        if current_close < current_ema and slope < Decimal("0"):
            return Side.SELL
        return None

    def _entry_side(
        self,
        *,
        trend: Side,
        previous: BarEvent,
        current: BarEvent,
        ema20: Decimal,
    ) -> Side | None:
        tolerance = self.config.pullback_tolerance
        if trend == Side.BUY:
            pulled_back = previous.low <= ema20 + tolerance
            confirmed = current.close > current.open and current.close > previous.high
            return Side.BUY if pulled_back and confirmed else None
        if trend == Side.SELL:
            pulled_back = previous.high >= ema20 - tolerance
            confirmed = current.close < current.open and current.close < previous.low
            return Side.SELL if pulled_back and confirmed else None
        return None

    def _log_block(self, bar: BarEvent, reason: str, **extra: str) -> None:
        LOGGER.info(
            "baseline signal blocked",
            extra={
                "event": "strategy.signal_blocked",
                "strategy_id": "baseline-xauusd-v1",
                "timestamp": bar.timestamp.isoformat(),
                "reason": reason,
                **extra,
            },
        )


def calculate_stop_target(
    *,
    side: Side,
    entry_price: Decimal,
    previous_bar: BarEvent,
    confirmation_bar: BarEvent,
    atr_value: Decimal,
    atr_floor_multiplier: Decimal,
    reward_risk: Decimal,
) -> StopTarget:
    """Calculate swing-based stop and fixed-R target."""

    atr_floor = atr_value * atr_floor_multiplier
    if side == Side.BUY:
        swing_stop = min(previous_bar.low, confirmation_bar.low)
        floor_stop = entry_price - atr_floor
        stop_loss = min(swing_stop, floor_stop)
        risk = entry_price - stop_loss
        take_profit = entry_price + (risk * reward_risk)
        return StopTarget(stop_loss=stop_loss, take_profit=take_profit, risk_per_unit=risk)
    if side == Side.SELL:
        swing_stop = max(previous_bar.high, confirmation_bar.high)
        floor_stop = entry_price + atr_floor
        stop_loss = max(swing_stop, floor_stop)
        risk = stop_loss - entry_price
        take_profit = entry_price - (risk * reward_risk)
        return StopTarget(stop_loss=stop_loss, take_profit=take_profit, risk_per_unit=risk)
    raise ValueError("stop target side cannot be flat")
