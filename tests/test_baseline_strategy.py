"""Tests for the first deterministic XAU/USD baseline strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurus.backtest import BacktestConfig, BacktestEngine
from aurus.common.schemas import BarEvent, Side
from aurus.strategy import (
    BaselineDiagnostics,
    BaselineStrategyConfig,
    BaselineXauUsdStrategy,
    ConfirmationMode,
    EntryMode,
    LondonSubwindow,
    calculate_stop_target,
)

BASE_TIME = datetime(2026, 4, 21, 7, 0, tzinfo=UTC)


def make_bar(
    index: int,
    *,
    timeframe: str,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    spread: Decimal = Decimal("0.20"),
) -> BarEvent:
    step = timedelta(minutes=5) if timeframe == "5m" else timedelta(hours=1)
    return BarEvent(
        timestamp=BASE_TIME + (step * index),
        correlation_id=f"{timeframe}-{index}",
        instrument="XAU/USD",
        timeframe=timeframe,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=Decimal("1"),
        spread=spread,
    )


def context_bars(direction: Side) -> list[BarEvent]:
    bars: list[BarEvent] = []
    for index in range(8):
        close = (
            Decimal("100") + Decimal(index)
            if direction == Side.BUY
            else Decimal("100") - Decimal(index)
        )
        timestamp_index = index - 8
        bars.append(
            BarEvent(
                timestamp=BASE_TIME + timedelta(hours=timestamp_index),
                correlation_id=f"1h-{index}",
                instrument="XAU/USD",
                timeframe="1h",
                open=close,
                high=close + Decimal("0.5"),
                low=close - Decimal("0.5"),
                close=close,
                volume=Decimal("1"),
                spread=Decimal("0.20"),
            )
        )
    return bars


def long_execution_bars(spread: Decimal = Decimal("0.20")) -> list[BarEvent]:
    closes = [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"), Decimal("104")]
    bars = [
        make_bar(
            index,
            timeframe="5m",
            open_price=close,
            high=close + Decimal("0.4"),
            low=close - Decimal("0.4"),
            close=close,
            spread=spread,
        )
        for index, close in enumerate(closes)
    ]
    bars.append(
        make_bar(
            5,
            timeframe="5m",
            open_price=Decimal("103.8"),
            high=Decimal("104.2"),
            low=Decimal("102.5"),
            close=Decimal("103.0"),
            spread=spread,
        )
    )
    bars.append(
        make_bar(
            6,
            timeframe="5m",
            open_price=Decimal("103.1"),
            high=Decimal("105.2"),
            low=Decimal("103.0"),
            close=Decimal("104.8"),
            spread=spread,
        )
    )
    return bars


def late_london_long_execution_bars() -> list[BarEvent]:
    bars = long_execution_bars()
    return [
        make_bar(
            index + 48,
            timeframe=bar.timeframe,
            open_price=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            spread=bar.spread or Decimal("0.20"),
        )
        for index, bar in enumerate(bars)
    ]


def short_execution_bars() -> list[BarEvent]:
    closes = [Decimal("100"), Decimal("99"), Decimal("98"), Decimal("97"), Decimal("96")]
    bars = [
        make_bar(
            index,
            timeframe="5m",
            open_price=close,
            high=close + Decimal("0.4"),
            low=close - Decimal("0.4"),
            close=close,
        )
        for index, close in enumerate(closes)
    ]
    bars.append(
        make_bar(
            5,
            timeframe="5m",
            open_price=Decimal("96.2"),
            high=Decimal("97.5"),
            low=Decimal("95.8"),
            close=Decimal("97.0"),
        )
    )
    bars.append(
        make_bar(
            6,
            timeframe="5m",
            open_price=Decimal("96.9"),
            high=Decimal("97.0"),
            low=Decimal("94.8"),
            close=Decimal("95.2"),
        )
    )
    return bars


def config(
    *,
    context_ema_period: int = 3,
    execution_ema_period: int = 3,
    atr_period: int = 3,
    min_atr: Decimal = Decimal("0.50"),
    min_atr_strength: Decimal = Decimal("0"),
    regime_min_atr_strength: Decimal = Decimal("0"),
    min_trend_strength: Decimal = Decimal("0"),
    max_spread: Decimal = Decimal("0.50"),
    allowed_sessions: frozenset[str] | None = None,
    allowed_london_subwindows: frozenset[LondonSubwindow] | None = None,
    atr_stop_floor_multiplier: Decimal = Decimal("1"),
    reward_risk: Decimal = Decimal("2"),
    confirmation_mode: ConfirmationMode = "strict",
    entry_mode: EntryMode = "baseline",
    min_pullback_depth_atr: Decimal = Decimal("0"),
    min_pre_entry_extension_atr: Decimal = Decimal("0"),
    max_spread_to_risk: Decimal | None = None,
    continuation_pullback_tolerance: Decimal = Decimal("0.50"),
) -> BaselineStrategyConfig:
    return BaselineStrategyConfig(
        context_ema_period=context_ema_period,
        execution_ema_period=execution_ema_period,
        atr_period=atr_period,
        min_atr=min_atr,
        min_atr_strength=min_atr_strength,
        regime_min_atr_strength=regime_min_atr_strength,
        min_trend_strength=min_trend_strength,
        max_spread=max_spread,
        allowed_sessions=(
            allowed_sessions
            if allowed_sessions is not None
            else BaselineStrategyConfig().allowed_sessions
        ),
        allowed_london_subwindows=(
            allowed_london_subwindows
            if allowed_london_subwindows is not None
            else BaselineStrategyConfig().allowed_london_subwindows
        ),
        atr_stop_floor_multiplier=atr_stop_floor_multiplier,
        reward_risk=reward_risk,
        confirmation_mode=confirmation_mode,
        entry_mode=entry_mode,
        min_pullback_depth_atr=min_pullback_depth_atr,
        min_pre_entry_extension_atr=min_pre_entry_extension_atr,
        max_spread_to_risk=max_spread_to_risk,
        continuation_pullback_tolerance=continuation_pullback_tolerance,
    )


def test_long_signal_generation_and_backtester_integration() -> None:
    strategy = BaselineXauUsdStrategy(context_bars=context_bars(Side.BUY), config=config())
    bars = long_execution_bars()

    signals = strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.BUY
    assert signals[0].features["stop_loss"] == "102.5"
    assert signals[0].features["take_profit"] == "109.4"

    result = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(default_quantity=Decimal("1")),
    ).run(bars)
    assert any(
        event.signal_id == signals[0].signal_id
        for event in result.events
        if hasattr(event, "signal_id")
    )


def test_short_signal_generation() -> None:
    strategy = BaselineXauUsdStrategy(context_bars=context_bars(Side.SELL), config=config())

    signals = strategy(tuple(short_execution_bars()))

    assert len(signals) == 1
    assert signals[0].side == Side.SELL
    assert signals[0].features["stop_loss"] == "97.5"
    assert signals[0].features["take_profit"] == "90.6"


def test_strict_confirmation_is_default_and_requires_breakout() -> None:
    bars = long_execution_bars()
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("103.1"),
        high=Decimal("104.0"),
        low=Decimal("103.0"),
        close=Decimal("103.6"),
    )
    default_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(),
    )
    explicit_strict_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="strict"),
    )

    assert default_strategy(tuple(bars)) == []
    assert explicit_strict_strategy(tuple(bars)) == []


def test_relaxed_confirmation_requires_only_directional_candle() -> None:
    bars = long_execution_bars()
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("103.1"),
        high=Decimal("104.0"),
        low=Decimal("103.0"),
        close=Decimal("103.6"),
    )
    diagnostics = BaselineDiagnostics()
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed"),
        diagnostics=diagnostics,
    )

    signals = strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.BUY
    assert signals[0].features["confirmation_mode"] == "relaxed"
    assert diagnostics.confirmation_pass == 1
    assert diagnostics.final_signal_emission == 1


def test_relaxed_short_confirmation_requires_only_directional_candle() -> None:
    bars = short_execution_bars()
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("96.9"),
        high=Decimal("97.0"),
        low=Decimal("96.0"),
        close=Decimal("96.4"),
    )
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.SELL),
        config=config(confirmation_mode="relaxed"),
    )

    signals = strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.SELL
    assert signals[0].features["confirmation_mode"] == "relaxed"


def test_early_momentum_long_does_not_require_pullback() -> None:
    bars = long_execution_bars()
    bars[-2] = make_bar(
        5,
        timeframe="5m",
        open_price=Decimal("104.8"),
        high=Decimal("105.2"),
        low=Decimal("104.6"),
        close=Decimal("105.0"),
    )
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("105.1"),
        high=Decimal("105.9"),
        low=Decimal("105.0"),
        close=Decimal("105.7"),
    )
    baseline_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed"),
    )
    early_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed", entry_mode="early_momentum"),
    )

    assert baseline_strategy(tuple(bars)) == []
    signals = early_strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.BUY
    assert signals[0].features["entry_mode"] == "early_momentum"


def test_early_momentum_short_does_not_require_pullback() -> None:
    bars = short_execution_bars()
    bars[-2] = make_bar(
        5,
        timeframe="5m",
        open_price=Decimal("95.2"),
        high=Decimal("95.4"),
        low=Decimal("94.8"),
        close=Decimal("95.0"),
    )
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("94.9"),
        high=Decimal("95.0"),
        low=Decimal("94.1"),
        close=Decimal("94.3"),
    )
    baseline_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.SELL),
        config=config(confirmation_mode="relaxed"),
    )
    early_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.SELL),
        config=config(confirmation_mode="relaxed", entry_mode="early_momentum"),
    )

    assert baseline_strategy(tuple(bars)) == []
    signals = early_strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.SELL
    assert signals[0].features["entry_mode"] == "early_momentum"


def test_early_momentum_requires_price_on_trend_side_of_ema() -> None:
    bars = long_execution_bars()
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("102.5"),
        high=Decimal("102.8"),
        low=Decimal("102.0"),
        close=Decimal("102.7"),
    )
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed", entry_mode="early_momentum"),
    )

    assert strategy(tuple(bars)) == []


def test_trend_continuation_accepts_directional_candle_without_pullback() -> None:
    bars = long_execution_bars()
    bars[-2] = make_bar(
        5,
        timeframe="5m",
        open_price=Decimal("104.8"),
        high=Decimal("105.2"),
        low=Decimal("104.6"),
        close=Decimal("105.0"),
    )
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("105.1"),
        high=Decimal("105.9"),
        low=Decimal("105.0"),
        close=Decimal("105.7"),
    )
    baseline_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed"),
    )
    continuation_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed", entry_mode="trend_continuation"),
    )

    assert baseline_strategy(tuple(bars)) == []
    signals = continuation_strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.BUY
    assert signals[0].features["entry_mode"] == "trend_continuation"


def test_trend_continuation_accepts_ema_band_pullback_without_directional_candle() -> None:
    bars = long_execution_bars()
    bars[-2] = make_bar(
        5,
        timeframe="5m",
        open_price=Decimal("104.8"),
        high=Decimal("105.2"),
        low=Decimal("104.6"),
        close=Decimal("105.0"),
    )
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("104.4"),
        high=Decimal("104.6"),
        low=Decimal("103.8"),
        close=Decimal("104.2"),
    )
    baseline_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed"),
    )
    early_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed", entry_mode="early_momentum"),
    )
    continuation_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed", entry_mode="trend_continuation"),
    )

    assert baseline_strategy(tuple(bars)) == []
    assert early_strategy(tuple(bars)) == []
    signals = continuation_strategy(tuple(bars))

    assert len(signals) == 1
    assert signals[0].side == Side.BUY
    assert signals[0].features["entry_mode"] == "trend_continuation"
    assert signals[0].features["continuation_pullback_tolerance"] == "0.50"


def test_trend_continuation_requires_price_on_trend_side_of_ema() -> None:
    bars = long_execution_bars()
    bars[-1] = make_bar(
        6,
        timeframe="5m",
        open_price=Decimal("102.5"),
        high=Decimal("102.8"),
        low=Decimal("102.0"),
        close=Decimal("102.7"),
    )
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(confirmation_mode="relaxed", entry_mode="trend_continuation"),
    )

    assert strategy(tuple(bars)) == []


def test_blocked_signal_under_spread_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(max_spread=Decimal("0.10")),
    )

    assert strategy(tuple(long_execution_bars(spread=Decimal("0.20")))) == []


def test_blocked_signal_under_atr_strength_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_atr_strength=Decimal("0.02")),
    )

    assert strategy(tuple(long_execution_bars())) == []


def test_blocked_signal_under_regime_atr_strength_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(regime_min_atr_strength=Decimal("0.02")),
    )

    assert strategy(tuple(long_execution_bars())) == []


def test_regime_atr_strength_is_recorded_on_signal() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(regime_min_atr_strength=Decimal("0.001")),
    )

    signals = strategy(tuple(long_execution_bars()))

    assert len(signals) == 1
    assert signals[0].features["regime_min_atr_strength"] == "0.001"
    assert Decimal(str(signals[0].features["regime_atr_strength"])) > Decimal("0.001")


def test_blocked_signal_under_trend_strength_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_trend_strength=Decimal("0.05")),
    )

    assert strategy(tuple(long_execution_bars())) == []


def test_blocked_signal_under_min_pullback_depth_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_pullback_depth_atr=Decimal("0.50")),
    )

    assert strategy(tuple(long_execution_bars())) == []


def test_pullback_depth_is_recorded_on_signal() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_pullback_depth_atr=Decimal("0.25")),
    )

    signals = strategy(tuple(long_execution_bars()))

    assert len(signals) == 1
    assert signals[0].features["min_pullback_depth_atr"] == "0.25"
    assert Decimal(str(signals[0].features["pullback_depth_atr"])) >= Decimal("0.25")


def test_blocked_signal_under_min_pre_entry_extension_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_pre_entry_extension_atr=Decimal("2.00")),
    )

    assert strategy(tuple(long_execution_bars())) == []


def test_pre_entry_extension_is_recorded_on_signal() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_pre_entry_extension_atr=Decimal("0.50")),
    )

    signals = strategy(tuple(long_execution_bars()))

    assert len(signals) == 1
    assert signals[0].features["min_pre_entry_extension_atr"] == "0.50"
    assert Decimal(str(signals[0].features["pre_entry_extension_atr"])) > Decimal("0.50")


def test_blocked_signal_under_spread_to_risk_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(max_spread_to_risk=Decimal("0.05")),
    )

    assert strategy(tuple(long_execution_bars(spread=Decimal("0.20")))) == []


def test_spread_to_risk_is_recorded_on_signal() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(max_spread_to_risk=Decimal("0.20")),
    )

    signals = strategy(tuple(long_execution_bars(spread=Decimal("0.20"))))

    assert len(signals) == 1
    assert signals[0].features["max_spread_to_risk"] == "0.20"
    assert Decimal(str(signals[0].features["spread_to_risk"])) <= Decimal("0.20")


def test_trend_strength_is_recorded_on_signal() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(min_trend_strength=Decimal("0.001")),
    )

    signals = strategy(tuple(long_execution_bars()))

    assert len(signals) == 1
    assert signals[0].features["min_trend_strength"] == "0.001"
    assert Decimal(str(signals[0].features["trend_strength"])) > Decimal("0.001")


def test_blocked_signal_under_session_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(allowed_sessions=frozenset({"new_york"})),
    )

    assert strategy(tuple(long_execution_bars())) == []


def test_blocked_signal_under_late_london_subwindow_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(allowed_london_subwindows=frozenset({"open", "mid"})),
    )

    assert strategy(tuple(late_london_long_execution_bars())) == []


def test_london_subwindow_is_recorded_on_signal() -> None:
    strategy = BaselineXauUsdStrategy(context_bars=context_bars(Side.BUY), config=config())

    signals = strategy(tuple(long_execution_bars()))

    assert len(signals) == 1
    assert signals[0].features["london_subwindow"] == "open"


def test_baseline_diagnostics_preserve_strategy_output() -> None:
    diagnostics = BaselineDiagnostics()
    plain_strategy = BaselineXauUsdStrategy(context_bars=context_bars(Side.BUY), config=config())
    diagnostic_strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(),
        diagnostics=diagnostics,
    )
    bars = long_execution_bars()

    plain_signals = plain_strategy(tuple(bars))
    diagnostic_signals = diagnostic_strategy(tuple(bars))

    assert diagnostic_signals == plain_signals
    assert diagnostics.candidate_bars == 1
    assert diagnostics.session_pass == 1
    assert diagnostics.spread_pass == 1
    assert diagnostics.volatility_pass == 1
    assert diagnostics.context_trend_pass == 1
    assert diagnostics.trend_quality_pass == 1
    assert diagnostics.pullback_pass == 1
    assert diagnostics.confirmation_pass == 1
    assert diagnostics.final_signal_emission == 1


def test_stop_target_calculations_for_long_and_short() -> None:
    previous_long = long_execution_bars()[5]
    current_long = long_execution_bars()[6]
    long_target = calculate_stop_target(
        side=Side.BUY,
        entry_price=current_long.close,
        previous_bar=previous_long,
        confirmation_bar=current_long,
        atr_value=Decimal("1.0"),
        atr_floor_multiplier=Decimal("1"),
        reward_risk=Decimal("2"),
    )
    assert long_target.stop_loss == Decimal("102.5")
    assert long_target.take_profit == Decimal("109.4")
    assert long_target.risk_per_unit == Decimal("2.3")

    previous_short = short_execution_bars()[5]
    current_short = short_execution_bars()[6]
    short_target = calculate_stop_target(
        side=Side.SELL,
        entry_price=current_short.close,
        previous_bar=previous_short,
        confirmation_bar=current_short,
        atr_value=Decimal("1.0"),
        atr_floor_multiplier=Decimal("1"),
        reward_risk=Decimal("2"),
    )
    assert short_target.stop_loss == Decimal("97.5")
    assert short_target.take_profit == Decimal("90.6")
    assert short_target.risk_per_unit == Decimal("2.3")
