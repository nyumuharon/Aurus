"""Tests for structural setup scanner helpers."""

from datetime import UTC, datetime

from aurus.backtest.scan_structural_setups import (
    TradeCandidate,
    format_top_results,
    max_drawdown,
    monthly_pnl,
    parse_timestamp,
    profit_factor,
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
