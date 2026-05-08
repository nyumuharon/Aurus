"""Tests for structural setup scanner helpers."""

from datetime import UTC, datetime

from aurus.backtest.scan_structural_setups import (
    HourBar,
    ResearchBar,
    ResearchData,
    TradeCandidate,
    format_top_results,
    max_drawdown,
    monthly_pnl,
    parse_timestamp,
    profit_factor,
    scan_compression_breakout,
    scan_session_run_reversal,
    summarize_trades,
)


def test_parse_timestamp_normalizes_zulu_time() -> None:
    timestamp = parse_timestamp("2026-04-23T10:00:00Z")

    assert timestamp == datetime(2026, 4, 23, 10, 0, tzinfo=UTC)


def test_profit_factor_and_drawdown() -> None:
    values = (10.0, -5.0, 2.0, -1.0)

    assert profit_factor(values) == 2.0
    assert max_drawdown(values) == 5.0


def test_monthly_pnl_and_summary() -> None:
    trades = (
        trade(datetime(2026, 1, 2, tzinfo=UTC), 10.0, 1.0),
        trade(datetime(2026, 1, 3, tzinfo=UTC), -3.0, -0.3),
        trade(datetime(2026, 2, 1, tzinfo=UTC), 5.0, 0.5),
    )

    summary = summarize_trades(setup="opening_range_breakout:test", trades=trades)

    assert monthly_pnl(trades) == {"2026-01": 7.0, "2026-02": 5.0}
    assert summary.setup == "opening_range_breakout"
    assert summary.trades == 3
    assert summary.net_pnl == 12.0
    assert summary.average_monthly_pnl == 6.0
    assert summary.positive_months == 2
    assert "opening_range_breakout" in format_top_results([summary])


def trade(exit_timestamp: datetime, pnl: float, realized_r: float) -> TradeCandidate:
    """Build a completed research trade."""

    return TradeCandidate(
        setup="test",
        entry_timestamp=exit_timestamp,
        exit_timestamp=exit_timestamp,
        side=1,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        risk_per_unit=10.0,
        pnl=pnl,
        realized_r=realized_r,
        exit_reason="time",
    )


def test_scan_compression_breakout_finds_first_break() -> None:
    bars = (
        bar(0, datetime(2026, 1, 1, 5, 0, tzinfo=UTC), 100.0, 100.4, 99.9, 100.2),
        bar(1, datetime(2026, 1, 1, 5, 5, tzinfo=UTC), 100.2, 100.3, 100.0, 100.1),
        bar(2, datetime(2026, 1, 1, 5, 10, tzinfo=UTC), 100.1, 100.4, 100.0, 100.2),
        bar(3, datetime(2026, 1, 1, 5, 15, tzinfo=UTC), 100.2, 100.3, 100.1, 100.2),
        bar(4, datetime(2026, 1, 1, 5, 20, tzinfo=UTC), 100.2, 100.4, 100.1, 100.3),
        bar(5, datetime(2026, 1, 1, 5, 25, tzinfo=UTC), 100.3, 100.35, 100.1, 100.2),
        bar(6, datetime(2026, 1, 1, 6, 0, tzinfo=UTC), 100.2, 101.2, 100.2, 101.0),
        bar(7, datetime(2026, 1, 1, 6, 5, tzinfo=UTC), 101.0, 102.0, 100.9, 101.8),
        bar(8, datetime(2026, 1, 1, 6, 10, tzinfo=UTC), 101.8, 101.9, 101.2, 101.5),
        bar(9, datetime(2026, 1, 1, 6, 15, tzinfo=UTC), 101.5, 101.7, 101.1, 101.6),
        bar(10, datetime(2026, 1, 1, 6, 20, tzinfo=UTC), 101.6, 101.8, 101.3, 101.7),
        bar(11, datetime(2026, 1, 1, 6, 25, tzinfo=UTC), 101.7, 101.9, 101.4, 101.8),
    )
    data = ResearchData(
        bars=bars,
        bars_by_day={datetime(2026, 1, 1, tzinfo=UTC): bars},
        hour_bars=(
            HourBar(
                timestamp=datetime(2026, 1, 1, 6, 0, tzinfo=UTC), high=101.0, low=99.0, close=100.0
            ),
        ),
        hour_timestamps=(datetime(2026, 1, 1, 6, 0, tzinfo=UTC),),
        hour_ema=(99.0,),
        hour_atr=(1.0,),
    )

    trades = scan_compression_breakout(
        data=data,
        compression_start_hour=5,
        compression_end_hour=6,
        breakout_end_hour=7,
        max_range_atr=0.75,
        reward_risk=2.0,
        setup="compression:test",
    )

    assert len(trades) == 1
    assert trades[0].side == 1


def test_scan_session_run_reversal_fades_extended_session_move() -> None:
    bars = (
        bar(0, datetime(2026, 1, 1, 7, 0, tzinfo=UTC), 100.0, 100.5, 99.9, 100.4),
        bar(1, datetime(2026, 1, 1, 7, 5, tzinfo=UTC), 100.4, 100.6, 100.3, 100.5),
        bar(2, datetime(2026, 1, 1, 13, 0, tzinfo=UTC), 103.0, 103.2, 102.8, 103.1),
        bar(3, datetime(2026, 1, 1, 13, 55, tzinfo=UTC), 103.1, 103.2, 102.4, 102.5),
        bar(4, datetime(2026, 1, 1, 14, 0, tzinfo=UTC), 102.5, 102.6, 101.5, 101.6),
        bar(5, datetime(2026, 1, 1, 14, 5, tzinfo=UTC), 101.6, 101.7, 100.0, 100.5),
    )
    data = ResearchData(
        bars=bars,
        bars_by_day={datetime(2026, 1, 1, tzinfo=UTC): bars},
        hour_bars=(
            HourBar(
                timestamp=datetime(2026, 1, 1, 13, 0, tzinfo=UTC), high=103.2, low=99.0, close=102.5
            ),
        ),
        hour_timestamps=(datetime(2026, 1, 1, 13, 0, tzinfo=UTC),),
        hour_ema=(101.0,),
        hour_atr=(1.0,),
    )

    trades = scan_session_run_reversal(
        data=data,
        open_hour=7,
        signal_hour=13,
        exit_hour=22,
        run_atr=2.0,
        reward_risk=2.5,
        setup="session_run_reversal:test",
    )

    assert len(trades) == 1
    assert trades[0].side == -1


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
