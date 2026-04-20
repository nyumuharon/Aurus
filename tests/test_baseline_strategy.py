"""Tests for the first deterministic XAU/USD baseline strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurus.backtest import BacktestConfig, BacktestEngine
from aurus.common.schemas import BarEvent, Side
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy, calculate_stop_target

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


def config(**overrides: object) -> BaselineStrategyConfig:
    values = {
        "context_ema_period": 3,
        "execution_ema_period": 3,
        "atr_period": 3,
        "min_atr": Decimal("0.50"),
        "max_spread": Decimal("0.50"),
        "atr_stop_floor_multiplier": Decimal("1"),
        "reward_risk": Decimal("2"),
    }
    values.update(overrides)
    return BaselineStrategyConfig(**values)


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


def test_blocked_signal_under_spread_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(max_spread=Decimal("0.10")),
    )

    assert strategy(tuple(long_execution_bars(spread=Decimal("0.20")))) == []


def test_blocked_signal_under_session_filter() -> None:
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars(Side.BUY),
        config=config(allowed_sessions=frozenset({"new_york"})),
    )

    assert strategy(tuple(long_execution_bars())) == []


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
