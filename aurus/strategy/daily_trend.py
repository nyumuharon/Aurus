"""Daily London-open trend strategy for XAU/USD."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from aurus.common.schemas import BarEvent, Side, SignalEvent, SourceMetadata
from aurus.strategy.indicators import atr, ema

DAILY_TREND_SOURCE = SourceMetadata(name="daily-london-trend-v1", kind="strategy")


@dataclass(frozen=True)
class DailyLondonTrendConfig:
    """Configuration for one-trade-per-day London trend continuation."""

    instrument: str = "XAU/USD"
    execution_timeframe: str = "5m"
    context_timeframe: str = "1h"
    context_ema_period: int = 20
    context_atr_period: int = 14
    entry_hour_utc: int = 7
    entry_minute_utc: int = 0
    exit_hour_utc: int = 20
    exit_minute_utc: int = 0
    atr_stop_multiplier: Decimal = Decimal("3")
    reward_risk: Decimal = Decimal("1.5")
    quantity: Decimal = Decimal("1")


class DailyLondonTrendStrategy:
    """Emit one daily London-open trade in the 1H EMA trend direction."""

    def __init__(
        self,
        *,
        context_bars: list[BarEvent],
        config: DailyLondonTrendConfig | None = None,
    ) -> None:
        self.config = config or DailyLondonTrendConfig()
        self.context_bars = sorted(
            [bar for bar in context_bars if self._is_context_bar(bar)],
            key=lambda bar: bar.timestamp,
        )
        self._context_timestamps = [bar.timestamp for bar in self.context_bars]
        self._context_ema_values = ema(
            [bar.close for bar in self.context_bars],
            self.config.context_ema_period,
        )
        self._context_atr_values = atr(self.context_bars, self.config.context_atr_period)

    def __call__(self, bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if not bars:
            return []

        current = bars[-1]
        if not self._is_execution_bar(current):
            return []
        if (
            current.timestamp.hour == self.config.exit_hour_utc
            and current.timestamp.minute == self.config.exit_minute_utc
        ):
            return [
                SignalEvent(
                    timestamp=current.timestamp,
                    correlation_id=f"daily-trend-exit-{current.correlation_id}",
                    source=DAILY_TREND_SOURCE,
                    signal_id=f"daily-trend-exit-{current.timestamp.isoformat()}",
                    strategy_id="daily-london-trend-v1",
                    instrument=current.instrument,
                    side=Side.FLAT,
                    strength=Decimal("0"),
                    reason="daily_london_trend_session_exit",
                    features={"quantity": str(self.config.quantity)},
                )
            ]

        if (
            current.timestamp.hour != self.config.entry_hour_utc
            or current.timestamp.minute != self.config.entry_minute_utc
        ):
            return []

        context_index = bisect_right(self._context_timestamps, current.timestamp) - 1
        if context_index < max(self.config.context_ema_period, self.config.context_atr_period):
            return []

        context_bar = self.context_bars[context_index]
        ema_value = self._context_ema_values[context_index]
        atr_value = self._context_atr_values[context_index]
        side = trend_side(context_bar=context_bar, ema_value=ema_value)
        if side is None or atr_value <= Decimal("0"):
            return []

        entry_price = assumed_entry_price(current, side)
        risk_per_unit = atr_value * self.config.atr_stop_multiplier
        if side == Side.BUY:
            stop_loss = entry_price - risk_per_unit
            take_profit = entry_price + (risk_per_unit * self.config.reward_risk)
        else:
            stop_loss = entry_price + risk_per_unit
            take_profit = entry_price - (risk_per_unit * self.config.reward_risk)

        return [
            SignalEvent(
                timestamp=current.timestamp,
                correlation_id=f"daily-trend-{current.correlation_id}",
                source=DAILY_TREND_SOURCE,
                signal_id=f"daily-trend-{side.value}-{current.timestamp.isoformat()}",
                strategy_id="daily-london-trend-v1",
                instrument=current.instrument,
                side=side,
                strength=Decimal("1"),
                reason="daily_london_open_1h_ema_trend",
                features={
                    "context_ema_period": self.config.context_ema_period,
                    "context_atr_period": self.config.context_atr_period,
                    "context_close": str(context_bar.close),
                    "context_ema": str(ema_value),
                    "context_atr": str(atr_value),
                    "atr_stop_multiplier": str(self.config.atr_stop_multiplier),
                    "stop_loss": str(stop_loss),
                    "take_profit": str(take_profit),
                    "risk_per_unit": str(risk_per_unit),
                    "reward_risk": str(self.config.reward_risk),
                    "quantity": str(self.config.quantity),
                },
            )
        ]

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


def trend_side(*, context_bar: BarEvent, ema_value: Decimal) -> Side | None:
    """Return direction from context close relative to EMA."""

    if context_bar.close > ema_value:
        return Side.BUY
    if context_bar.close < ema_value:
        return Side.SELL
    return None


def assumed_entry_price(bar: BarEvent, side: Side) -> Decimal:
    """Match the backtester's no-slippage market entry assumption."""

    half_spread = (bar.spread or Decimal("0")) / Decimal("2")
    if side == Side.BUY:
        return bar.close + half_spread
    if side == Side.SELL:
        return bar.close - half_spread
    raise ValueError("entry side cannot be flat")
