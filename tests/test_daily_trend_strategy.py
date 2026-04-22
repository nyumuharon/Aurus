"""Tests for the daily London trend strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurus.common.schemas import BarEvent, Side
from aurus.strategy import DailyLondonTrendConfig, DailyLondonTrendStrategy, DailyTrendWindow

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
    assert signals[0].features["window_label"] == "london"
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
        strategy([bar(BASE_TIME + timedelta(minutes=5), timeframe="5m", close=Decimal("130"))])
        == []
    )


def test_daily_trend_emits_flat_signal_at_session_exit() -> None:
    strategy = DailyLondonTrendStrategy(
        context_bars=context_bars(Side.BUY),
        config=DailyLondonTrendConfig(context_ema_period=20, context_atr_period=14),
    )

    signals = strategy([bar(BASE_TIME.replace(hour=20), timeframe="5m", close=Decimal("130"))])

    assert len(signals) == 1
    assert signals[0].side == Side.FLAT
    assert signals[0].reason == "daily_london_trend_session_exit"


def test_daily_trend_supports_multiple_configured_windows() -> None:
    strategy = DailyLondonTrendStrategy(
        context_bars=context_bars(Side.BUY),
        config=DailyLondonTrendConfig(
            context_ema_period=20,
            context_atr_period=14,
            windows=(
                DailyTrendWindow(label="london_morning", entry_hour_utc=7, exit_hour_utc=11),
                DailyTrendWindow(label="new_york_morning", entry_hour_utc=13, exit_hour_utc=17),
            ),
        ),
    )

    entry_signals = strategy(
        [bar(BASE_TIME.replace(hour=13), timeframe="5m", close=Decimal("130"))]
    )
    exit_signals = strategy([bar(BASE_TIME.replace(hour=17), timeframe="5m", close=Decimal("130"))])

    assert len(entry_signals) == 1
    assert entry_signals[0].side == Side.BUY
    assert entry_signals[0].features["window_label"] == "new_york_morning"
    assert len(exit_signals) == 1
    assert exit_signals[0].side == Side.FLAT
    assert exit_signals[0].features["window_label"] == "new_york_morning"
