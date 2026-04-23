"""Tests for deterministic channel-breakout scanner helpers."""

from datetime import UTC, datetime, timedelta

import pytest
from aurus.backtest.scan_channel_breakouts import (
    channel_risk,
    first_channel_breakout_trade,
)
from aurus.backtest.scan_structural_setups import ResearchBar


def test_channel_risk_modes() -> None:
    assert (
        channel_risk(
            channel_high=105.0,
            channel_low=100.0,
            context_atr=2.0,
            stop_mode="channel",
            atr_stop_multiplier=0.0,
        )
        == 5.0
    )
    assert (
        channel_risk(
            channel_high=105.0,
            channel_low=100.0,
            context_atr=2.0,
            stop_mode="half_channel",
            atr_stop_multiplier=0.0,
        )
        == 2.5
    )
    assert (
        channel_risk(
            channel_high=105.0,
            channel_low=100.0,
            context_atr=2.0,
            stop_mode="atr",
            atr_stop_multiplier=3.0,
        )
        == 6.0
    )


def test_channel_risk_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unsupported stop mode"):
        channel_risk(
            channel_high=105.0,
            channel_low=100.0,
            context_atr=2.0,
            stop_mode="unknown",
            atr_stop_multiplier=0.0,
        )


def test_first_channel_breakout_trade_enters_first_break() -> None:
    start = datetime(2026, 4, 23, 6, 0, tzinfo=UTC)
    bars = (
        bar(0, start, 100.0, 101.0, 99.5, 100.5),
        bar(1, start + timedelta(minutes=5), 101.0, 106.0, 100.5, 105.0),
        bar(2, start + timedelta(minutes=10), 105.0, 111.0, 104.0, 110.0),
    )

    trade = first_channel_breakout_trade(
        setup="test",
        trade_bars=bars,
        channel_high=105.0,
        channel_low=95.0,
        risk=2.0,
        reward_risk=2.0,
    )

    assert trade is not None
    assert trade.side == 1
    assert trade.entry_timestamp == bars[1].timestamp
    assert trade.exit_reason == "take_profit"


def bar(
    index: int,
    timestamp: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> ResearchBar:
    """Build a lightweight research bar."""

    return ResearchBar(
        index=index,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        spread=0.0,
    )
