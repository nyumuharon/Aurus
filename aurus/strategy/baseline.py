"""First deterministic XAU/USD baseline strategy."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from aurus.common.schemas import BarEvent, Side, SignalEvent, SourceMetadata
from aurus.data.sessions import TradingSession, tag_session
from aurus.strategy.indicators import atr, ema

LOGGER = logging.getLogger(__name__)
STRATEGY_SOURCE = SourceMetadata(name="baseline-xauusd-v1", kind="strategy")
ConfirmationMode = Literal["strict", "relaxed"]
EntryMode = Literal["baseline", "early_momentum", "trend_continuation"]
LondonSubwindow = Literal["open", "mid", "late"]
ALL_LONDON_SUBWINDOWS: frozenset[LondonSubwindow] = frozenset({"open", "mid", "late"})


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
    min_atr_strength: Decimal = Decimal("0")
    regime_min_atr_strength: Decimal = Decimal("0")
    min_trend_strength: Decimal = Decimal("0")
    max_spread: Decimal = Decimal("0.50")
    allowed_sessions: frozenset[str] = frozenset(
        {TradingSession.LONDON.value, TradingSession.NEW_YORK.value}
    )
    allowed_london_subwindows: frozenset[LondonSubwindow] = ALL_LONDON_SUBWINDOWS
    early_new_york_end_hour_utc: int = 16
    pullback_tolerance: Decimal = Decimal("0")
    min_pullback_depth_atr: Decimal = Decimal("0")
    continuation_pullback_tolerance: Decimal = Decimal("0.50")
    atr_stop_floor_multiplier: Decimal = Decimal("1")
    reward_risk: Decimal = Decimal("2")
    confirmation_mode: ConfirmationMode = "strict"
    entry_mode: EntryMode = "baseline"
    strength: Decimal = Decimal("1")
    quantity: Decimal = Decimal("1")


@dataclass(frozen=True)
class StopTarget:
    """Calculated protective stop and fixed-R target."""

    stop_loss: Decimal
    take_profit: Decimal
    risk_per_unit: Decimal


@dataclass
class BaselineDiagnostics:
    """Point-in-time rejection funnel for the baseline strategy."""

    strategy_calls: int = 0
    execution_bar_calls: int = 0
    insufficient_execution_history: int = 0
    candidate_bars: int = 0
    session_pass: int = 0
    session_reject: int = 0
    spread_pass: int = 0
    spread_reject: int = 0
    volatility_pass: int = 0
    volatility_reject: int = 0
    context_trend_pass: int = 0
    context_trend_reject: int = 0
    trend_quality_pass: int = 0
    trend_quality_reject: int = 0
    regime_filter_pass: int = 0
    regime_filter_reject: int = 0
    pullback_pass: int = 0
    pullback_reject: int = 0
    confirmation_pass: int = 0
    confirmation_reject: int = 0
    final_signal_emission: int = 0

    def observe(
        self,
        *,
        config: BaselineStrategyConfig,
        context_bars: list[BarEvent],
        bars: Sequence[BarEvent],
        emitted_signals: list[SignalEvent],
    ) -> None:
        """Count a sequential diagnostic funnel without changing strategy output."""

        self.strategy_calls += 1
        execution_bars = [
            bar
            for bar in bars
            if bar.instrument == config.instrument and bar.timeframe == config.execution_timeframe
        ]
        if not execution_bars:
            return

        self.execution_bar_calls += 1
        if len(execution_bars) < max(2, config.execution_ema_period, config.atr_period):
            self.insufficient_execution_history += 1
            return

        self.candidate_bars += 1
        current = execution_bars[-1]
        previous = execution_bars[-2]

        if _session_rejection_reason(current, config) is not None:
            self.session_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        self.session_pass += 1

        if _spread_rejection_reason(current, config) is not None:
            self.spread_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        self.spread_pass += 1

        current_atr = atr(execution_bars, config.atr_period)[-1]
        if current_atr < config.min_atr:
            self.volatility_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        if _atr_strength(current_atr=current_atr, current=current) < config.min_atr_strength:
            self.volatility_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        self.volatility_pass += 1

        context = [
            context_bar
            for context_bar in context_bars
            if context_bar.timestamp <= current.timestamp
        ]
        trend = _context_trend(context, config)
        if trend is None:
            self.context_trend_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        self.context_trend_pass += 1

        trend_strength = _context_trend_strength(context, config)
        if trend_strength is None or trend_strength < config.min_trend_strength:
            self.trend_quality_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        self.trend_quality_pass += 1

        regime_strength = _context_atr_strength(context, config.atr_period)
        if regime_strength is None or regime_strength < config.regime_min_atr_strength:
            self.regime_filter_reject += 1
            self.final_signal_emission += len(emitted_signals)
            return
        self.regime_filter_pass += 1

        execution_ema = ema([bar.close for bar in execution_bars], config.execution_ema_period)
        ema_value = execution_ema[-2]
        if config.entry_mode == "baseline":
            pullback_depth_atr = _pullback_depth_atr(
                trend=trend,
                previous=previous,
                ema_value=ema_value,
                atr_value=current_atr,
            )
            if not _has_pullback(
                trend=trend,
                previous=previous,
                ema_value=ema_value,
                pullback_depth_atr=pullback_depth_atr,
                config=config,
            ):
                self.pullback_reject += 1
                self.final_signal_emission += len(emitted_signals)
                return
            self.pullback_pass += 1

            if not _has_confirmation(
                trend=trend,
                previous=previous,
                current=current,
                mode=config.confirmation_mode,
            ):
                self.confirmation_reject += 1
                self.final_signal_emission += len(emitted_signals)
                return
            self.confirmation_pass += 1
        elif config.entry_mode == "early_momentum":
            if not _is_price_on_trend_side(
                trend=trend,
                current=current,
                ema_value=execution_ema[-1],
            ):
                self.pullback_reject += 1
                self.final_signal_emission += len(emitted_signals)
                return
            self.pullback_pass += 1

            if not _has_directional_confirmation(trend=trend, current=current):
                self.confirmation_reject += 1
                self.final_signal_emission += len(emitted_signals)
                return
            self.confirmation_pass += 1
        elif config.entry_mode == "trend_continuation":
            if not _has_trend_continuation_entry(
                trend=trend,
                current=current,
                ema_value=execution_ema[-1],
                config=config,
            ):
                self.pullback_reject += 1
                self.final_signal_emission += len(emitted_signals)
                return
            self.pullback_pass += 1
            self.confirmation_pass += 1
        else:
            raise ValueError(f"unsupported entry_mode: {config.entry_mode}")
        self.final_signal_emission += len(emitted_signals)

    def rejection_counts(self) -> dict[str, int]:
        """Return the stage rejection counts used for blocker diagnosis."""

        return {
            "insufficient_execution_history": self.insufficient_execution_history,
            "session_filter": self.session_reject,
            "spread_filter": self.spread_reject,
            "volatility_filter": self.volatility_reject,
            "context_trend_filter": self.context_trend_reject,
            "trend_quality_filter": self.trend_quality_reject,
            "regime_filter": self.regime_filter_reject,
            "pullback_condition": self.pullback_reject,
            "confirmation_candle_condition": self.confirmation_reject,
        }

    def biggest_blocker(self) -> tuple[str, int]:
        """Return the stage with the largest rejection count."""

        return max(self.rejection_counts().items(), key=lambda item: item[1])

    def format_summary(self) -> str:
        """Render a deterministic diagnostic summary."""

        biggest_name, biggest_count = self.biggest_blocker()
        return "\n".join(
            [
                "Baseline diagnostic rejection funnel",
                f"strategy calls: {self.strategy_calls}",
                f"execution bar calls: {self.execution_bar_calls}",
                f"insufficient execution history: {self.insufficient_execution_history}",
                f"candidate bars: {self.candidate_bars}",
                f"session filter pass: {self.session_pass}",
                f"session filter reject: {self.session_reject}",
                f"spread filter pass: {self.spread_pass}",
                f"spread filter reject: {self.spread_reject}",
                f"volatility filter pass: {self.volatility_pass}",
                f"volatility filter reject: {self.volatility_reject}",
                f"context trend filter pass: {self.context_trend_pass}",
                f"context trend filter reject: {self.context_trend_reject}",
                f"trend quality filter pass: {self.trend_quality_pass}",
                f"trend quality filter reject: {self.trend_quality_reject}",
                f"regime filter pass: {self.regime_filter_pass}",
                f"regime filter reject: {self.regime_filter_reject}",
                f"pullback condition pass: {self.pullback_pass}",
                f"pullback condition reject: {self.pullback_reject}",
                f"confirmation candle condition pass: {self.confirmation_pass}",
                f"confirmation candle condition reject: {self.confirmation_reject}",
                f"final signal emission: {self.final_signal_emission}",
                f"single biggest blocker: {biggest_name} ({biggest_count})",
            ]
        )

    def write_summary(self, path: Path) -> None:
        """Write the deterministic diagnostic summary to disk."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.format_summary() + "\n", encoding="utf-8")


class BaselineXauUsdStrategy:
    """Deterministic 1H trend plus 5M pullback baseline strategy."""

    def __init__(
        self,
        *,
        context_bars: list[BarEvent],
        config: BaselineStrategyConfig | None = None,
        diagnostics: BaselineDiagnostics | None = None,
    ) -> None:
        self.config = config or BaselineStrategyConfig()
        self.diagnostics = diagnostics
        self.context_bars = sorted(
            [bar for bar in context_bars if self._is_context_bar(bar)],
            key=lambda bar: bar.timestamp,
        )
        self._context_ema_values = ema(
            [bar.close for bar in self.context_bars],
            self.config.context_ema_period,
        )
        self._context_atr_values = atr(self.context_bars, self.config.atr_period)
        self._cached_execution_bars: list[BarEvent] = []
        self._cached_execution_ema: list[Decimal] = []
        self._cached_execution_atr: list[Decimal] = []
        self._cached_true_ranges: list[Decimal] = []

    def __call__(self, bars: Sequence[BarEvent]) -> list[SignalEvent]:
        signals = self._generate_signals(bars)
        if self.diagnostics is not None:
            self.diagnostics.observe(
                config=self.config,
                context_bars=self.context_bars,
                bars=bars,
                emitted_signals=signals,
            )
        return signals

    def _generate_signals(self, bars: Sequence[BarEvent]) -> list[SignalEvent]:
        execution_bars = self._execution_bars_from(bars)
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
        trend_strength = self._trend_strength(context)
        if trend_strength is None or trend_strength < self.config.min_trend_strength:
            self._log_block(
                current,
                "trend_strength_below_threshold",
                trend_strength=("unavailable" if trend_strength is None else str(trend_strength)),
            )
            return []
        regime_atr_strength = self._regime_atr_strength(context)
        if (
            regime_atr_strength is None
            or regime_atr_strength < self.config.regime_min_atr_strength
        ):
            self._log_block(
                current,
                "regime_atr_strength_below_threshold",
                regime_atr_strength=(
                    "unavailable" if regime_atr_strength is None else str(regime_atr_strength)
                ),
            )
            return []

        execution_ema, atr_values = self._indicator_values(execution_bars)
        current_atr = atr_values[-1]
        if current_atr < self.config.min_atr:
            self._log_block(current, "atr_below_threshold", atr=str(current_atr))
            return []
        current_atr_strength = _atr_strength(current_atr=current_atr, current=current)
        if current_atr_strength < self.config.min_atr_strength:
            self._log_block(
                current,
                "atr_strength_below_threshold",
                atr_strength=str(current_atr_strength),
            )
            return []

        entry_ema = (
            execution_ema[-1]
            if self.config.entry_mode in {"early_momentum", "trend_continuation"}
            else execution_ema[-2]
        )
        side = self._entry_side(
            trend=trend,
            previous=previous,
            current=current,
            ema20=entry_ema,
            atr_value=current_atr,
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
                "atr_strength": str(current_atr_strength),
                "min_atr_strength": str(self.config.min_atr_strength),
                "regime_atr_strength": str(regime_atr_strength),
                "regime_min_atr_strength": str(self.config.regime_min_atr_strength),
                "trend_strength": str(trend_strength),
                "min_trend_strength": str(self.config.min_trend_strength),
                "london_subwindow": _london_subwindow(current),
                "ema20": str(entry_ema),
                "pullback_depth_atr": str(
                    _pullback_depth_atr(
                        trend=side,
                        previous=previous,
                        ema_value=entry_ema,
                        atr_value=current_atr,
                    )
                ),
                "min_pullback_depth_atr": str(self.config.min_pullback_depth_atr),
                "stop_loss": str(stop_target.stop_loss),
                "take_profit": str(stop_target.take_profit),
                "risk_per_unit": str(stop_target.risk_per_unit),
                "reward_risk": str(self.config.reward_risk),
                "confirmation_mode": self.config.confirmation_mode,
                "entry_mode": self.config.entry_mode,
                "continuation_pullback_tolerance": str(
                    self.config.continuation_pullback_tolerance
                ),
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

    def _execution_bars_from(self, bars: Sequence[BarEvent]) -> Sequence[BarEvent]:
        if not bars:
            return ()
        if self._is_execution_bar(bars[0]) and self._is_execution_bar(bars[-1]):
            return bars
        return [bar for bar in bars if self._is_execution_bar(bar)]

    def _blocked_reason(self, bar: BarEvent) -> str | None:
        return _session_rejection_reason(bar, self.config) or _spread_rejection_reason(
            bar, self.config
        )

    def _context_until(self, bar: BarEvent) -> list[BarEvent]:
        return [
            context_bar
            for context_bar in self.context_bars
            if context_bar.timestamp <= bar.timestamp
        ]

    def _trend(self, context: list[BarEvent]) -> Side | None:
        if len(context) < self.config.context_ema_period + 1:
            return None

        context_index = len(context) - 1
        current_close = context[-1].close
        current_ema = self._context_ema_values[context_index]
        previous_ema = self._context_ema_values[context_index - 1]
        slope = current_ema - previous_ema

        if current_close > current_ema and slope > Decimal("0"):
            return Side.BUY
        if current_close < current_ema and slope < Decimal("0"):
            return Side.SELL
        return None

    def _regime_atr_strength(self, context: list[BarEvent]) -> Decimal | None:
        if not context:
            return None
        context_index = len(context) - 1
        return _atr_strength(
            current_atr=self._context_atr_values[context_index],
            current=context[-1],
        )

    def _trend_strength(self, context: list[BarEvent]) -> Decimal | None:
        if len(context) <= self.config.context_ema_period:
            return None
        context_index = len(context) - 1
        previous_index = context_index - self.config.context_ema_period
        slope = self._context_ema_values[context_index] - self._context_ema_values[previous_index]
        return abs(slope) / context[-1].close

    def _entry_side(
        self,
        *,
        trend: Side,
        previous: BarEvent,
        current: BarEvent,
        ema20: Decimal,
        atr_value: Decimal,
    ) -> Side | None:
        if trend in {Side.BUY, Side.SELL}:
            if self.config.entry_mode == "baseline":
                pullback_depth_atr = _pullback_depth_atr(
                    trend=trend,
                    previous=previous,
                    ema_value=ema20,
                    atr_value=atr_value,
                )
                pulled_back = _has_pullback(
                    trend=trend,
                    previous=previous,
                    ema_value=ema20,
                    pullback_depth_atr=pullback_depth_atr,
                    config=self.config,
                )
                confirmed = _has_confirmation(
                    trend=trend,
                    previous=previous,
                    current=current,
                    mode=self.config.confirmation_mode,
                )
                return trend if pulled_back and confirmed else None
            if self.config.entry_mode == "early_momentum":
                price_on_trend_side = _is_price_on_trend_side(
                    trend=trend,
                    current=current,
                    ema_value=ema20,
                )
                confirmed = _has_directional_confirmation(trend=trend, current=current)
                return trend if price_on_trend_side and confirmed else None
            if self.config.entry_mode == "trend_continuation":
                return (
                    trend
                    if _has_trend_continuation_entry(
                        trend=trend,
                        current=current,
                        ema_value=ema20,
                        config=self.config,
                    )
                    else None
                )
            raise ValueError(f"unsupported entry_mode: {self.config.entry_mode}")
        return None

    def _indicator_values(
        self,
        execution_bars: Sequence[BarEvent],
    ) -> tuple[list[Decimal], list[Decimal]]:
        self._sync_indicator_cache(execution_bars)
        return self._cached_execution_ema, self._cached_execution_atr

    def _sync_indicator_cache(self, execution_bars: Sequence[BarEvent]) -> None:
        if not self._can_extend_indicator_cache(execution_bars):
            self._cached_execution_bars = []
            self._cached_execution_ema = []
            self._cached_execution_atr = []
            self._cached_true_ranges = []

        start_index = len(self._cached_execution_bars)
        smoothing = Decimal("2") / Decimal(self.config.execution_ema_period + 1)
        for index in range(start_index, len(execution_bars)):
            current = execution_bars[index]
            self._cached_execution_bars.append(current)

            if index == 0:
                self._cached_execution_ema.append(current.close)
                self._cached_true_ranges.append(current.high - current.low)
            else:
                previous_ema = self._cached_execution_ema[-1]
                self._cached_execution_ema.append(
                    (current.close * smoothing) + (previous_ema * (Decimal("1") - smoothing))
                )
                previous = execution_bars[index - 1]
                self._cached_true_ranges.append(
                    max(
                        current.high - current.low,
                        abs(current.high - previous.close),
                        abs(current.low - previous.close),
                    )
                )

            atr_start = max(0, index + 1 - self.config.atr_period)
            atr_window = self._cached_true_ranges[atr_start : index + 1]
            self._cached_execution_atr.append(
                sum(atr_window, Decimal("0")) / Decimal(len(atr_window))
            )

    def _can_extend_indicator_cache(self, execution_bars: Sequence[BarEvent]) -> bool:
        cached_count = len(self._cached_execution_bars)
        if cached_count == 0:
            return True
        if len(execution_bars) < cached_count:
            return False
        if execution_bars[0] != self._cached_execution_bars[0]:
            return False
        return execution_bars[cached_count - 1] == self._cached_execution_bars[-1]

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


def _session_rejection_reason(bar: BarEvent, config: BaselineStrategyConfig) -> str | None:
    session = tag_session(bar.timestamp)
    if session.value not in config.allowed_sessions:
        return f"blocked_session:{session.value}"
    if session == TradingSession.LONDON:
        subwindow = _london_subwindow(bar)
        if subwindow not in config.allowed_london_subwindows:
            return f"blocked_london_subwindow:{subwindow}"
    if (
        session == TradingSession.NEW_YORK
        and bar.timestamp.hour >= config.early_new_york_end_hour_utc
    ):
        return "blocked_session:late_new_york"
    return None


def _london_subwindow(bar: BarEvent) -> LondonSubwindow | str:
    hour = bar.timestamp.hour
    if 7 <= hour < 9:
        return "open"
    if 9 <= hour < 11:
        return "mid"
    if 11 <= hour < 13:
        return "late"
    return "outside_london"


def _spread_rejection_reason(bar: BarEvent, config: BaselineStrategyConfig) -> str | None:
    if bar.spread is None:
        return "missing_spread"
    if bar.spread > config.max_spread:
        return "spread_above_threshold"
    return None


def _context_trend(context: list[BarEvent], config: BaselineStrategyConfig) -> Side | None:
    if len(context) < config.context_ema_period + 1:
        return None

    closes = [bar.close for bar in context]
    ema_values = ema(closes, config.context_ema_period)
    current_close = closes[-1]
    current_ema = ema_values[-1]
    previous_ema = ema_values[-2]
    slope = current_ema - previous_ema

    if current_close > current_ema and slope > Decimal("0"):
        return Side.BUY
    if current_close < current_ema and slope < Decimal("0"):
        return Side.SELL
    return None


def _context_atr_strength(context: list[BarEvent], atr_period: int) -> Decimal | None:
    if not context:
        return None
    atr_values = atr(context, atr_period)
    return _atr_strength(current_atr=atr_values[-1], current=context[-1])


def _context_trend_strength(
    context: list[BarEvent],
    config: BaselineStrategyConfig,
) -> Decimal | None:
    if len(context) <= config.context_ema_period:
        return None
    ema_values = ema([bar.close for bar in context], config.context_ema_period)
    slope = ema_values[-1] - ema_values[-1 - config.context_ema_period]
    return abs(slope) / context[-1].close


def _has_pullback(
    *,
    trend: Side,
    previous: BarEvent,
    ema_value: Decimal,
    pullback_depth_atr: Decimal,
    config: BaselineStrategyConfig,
) -> bool:
    tolerance = config.pullback_tolerance
    if trend == Side.BUY:
        touched_ema = previous.low <= ema_value + tolerance
        return touched_ema and pullback_depth_atr >= config.min_pullback_depth_atr
    if trend == Side.SELL:
        touched_ema = previous.high >= ema_value - tolerance
        return touched_ema and pullback_depth_atr >= config.min_pullback_depth_atr
    return False


def _pullback_depth_atr(
    *,
    trend: Side,
    previous: BarEvent,
    ema_value: Decimal,
    atr_value: Decimal,
) -> Decimal:
    if atr_value <= Decimal("0"):
        return Decimal("0")
    if trend == Side.BUY:
        return max(Decimal("0"), ema_value - previous.low) / atr_value
    if trend == Side.SELL:
        return max(Decimal("0"), previous.high - ema_value) / atr_value
    return Decimal("0")


def _has_confirmation(
    *,
    trend: Side,
    previous: BarEvent,
    current: BarEvent,
    mode: ConfirmationMode,
) -> bool:
    if mode not in {"strict", "relaxed"}:
        raise ValueError(f"unsupported confirmation_mode: {mode}")

    if trend == Side.BUY:
        direction_confirmed = current.close > current.open
        if mode == "relaxed":
            return direction_confirmed
        return direction_confirmed and current.close > previous.high
    if trend == Side.SELL:
        direction_confirmed = current.close < current.open
        if mode == "relaxed":
            return direction_confirmed
        return direction_confirmed and current.close < previous.low
    return False


def _has_directional_confirmation(*, trend: Side, current: BarEvent) -> bool:
    if trend == Side.BUY:
        return current.close > current.open
    if trend == Side.SELL:
        return current.close < current.open
    return False


def _is_price_on_trend_side(*, trend: Side, current: BarEvent, ema_value: Decimal) -> bool:
    if trend == Side.BUY:
        return current.close > ema_value
    if trend == Side.SELL:
        return current.close < ema_value
    return False


def _atr_strength(*, current_atr: Decimal, current: BarEvent) -> Decimal:
    return current_atr / current.close


def _is_within_ema_pullback_band(
    *,
    trend: Side,
    current: BarEvent,
    ema_value: Decimal,
    tolerance: Decimal,
) -> bool:
    lower_bound = ema_value - tolerance
    upper_bound = ema_value + tolerance
    if trend == Side.BUY:
        return lower_bound <= current.low <= upper_bound
    if trend == Side.SELL:
        return lower_bound <= current.high <= upper_bound
    return False


def _has_trend_continuation_entry(
    *,
    trend: Side,
    current: BarEvent,
    ema_value: Decimal,
    config: BaselineStrategyConfig,
) -> bool:
    if not _is_price_on_trend_side(trend=trend, current=current, ema_value=ema_value):
        return False
    return _has_directional_confirmation(trend=trend, current=current) or (
        _is_within_ema_pullback_band(
            trend=trend,
            current=current,
            ema_value=ema_value,
            tolerance=config.continuation_pullback_tolerance,
        )
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
