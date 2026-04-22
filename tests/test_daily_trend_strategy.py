"""Tests for the daily London trend strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurus.common.schemas import BarEvent, Side
from aurus.strategy import DailyLondonTrendConfig, DailyLondonTrendStrategy

BASE_TIME = datetime(2026, 4, 21, 7, 0, tzinfo=UTC)


def bar(
    timestamp: datetime,
    *,
    timeframe: str,
    close: Decimal,
    spread: Decimal = Decimal("0.40"),
) -> BarEvent:
    return BarEvent(
        timestamp=timestamp,
        correlation_id=f"{timeframe}-{timestamp.isoformat()}",
        instrument="XAU/USD",
        timeframe=timeframe,
        open=close,
        high=close + Decimal("1"),
        low=close - Decimal("1"),
        close=close,
        volume=Decimal("1"),
        spread=spread,
    )


def context_bars(direction: Side) -> list[BarEvent]:
    bars: list[BarEvent] = []
    for index in range(30):
        close = (
            Decimal("100") + Decimal(index)
            if direction == Side.BUY
            else Decimal("130") - Decimal(index)
        )
        bars.append(
            bar(
                BASE_TIME - timedelta(hours=30 - index),
                timeframe="1h",
                close=close,
            )
        )
    return bars


def test_daily_trend_emits_one_london_open_long_signal() -> None:
    strategy = DailyLondonTrendStrategy(
        context_bars=context_bars(Side.BUY),
        config=DailyLondonTrendConfig(context_ema_period=20, context_atr_period=14),
    )
    execution_bar = bar(BASE_TIME, timeframe="5m", close=Decimal("130"))

    signals = strategy([execution_bar])

    assert len(signals) == 1
    assert signals[0].side == Side.BUY
    assert signals[0].features["reward_risk"] == "1.5"
    assert Decimal(str(signals[0].features["risk_per_unit"])) > Decimal("0")


def test_daily_trend_emits_short_signal_below_context_ema() -> None:
    strategy = DailyLondonTrendStrategy(
        context_bars=context_bars(Side.SELL),
        config=DailyLondonTrendConfig(context_ema_period=20, context_atr_period=14),
    )

    signals = strategy([bar(BASE_TIME, timeframe="5m", close=Decimal("100"))])

    assert len(signals) == 1
    assert signals[0].side == Side.SELL


def test_daily_trend_only_trades_configured_entry_time() -> None:
    strategy = DailyLondonTrendStrategy(
        context_bars=context_bars(Side.BUY),
        config=DailyLondonTrendConfig(context_ema_period=20, context_atr_period=14),
    )

    assert (
        strategy(
            [bar(BASE_TIME + timedelta(minutes=5), timeframe="5m", close=Decimal("130"))]
        )
        == []
    )
