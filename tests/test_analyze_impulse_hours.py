"""Tests for impulse-hour analysis."""

from datetime import UTC, datetime

from aurus.backtest.analyze_impulse_hours import (
    format_impulse_hour_rows,
    hour_rows,
)
from aurus.backtest.scan_structural_setups import TradeCandidate


def test_hour_rows_groups_impulse_trades_by_entry_hour() -> None:
    rows = hour_rows(
        parameters="impulse_continuation:test",
        trades=(
            trade(datetime(2026, 4, 23, 6, tzinfo=UTC), 10.0, 1.0),
            trade(datetime(2026, 4, 24, 6, tzinfo=UTC), -4.0, -0.4),
            trade(datetime(2026, 4, 23, 13, tzinfo=UTC), 5.0, 0.5),
        ),
    )

    assert [row.entry_hour_utc for row in rows] == [6, 13]
    assert rows[0].trades == 2
    assert rows[0].net_pnl == 6.0
    assert rows[1].trades == 1
    assert rows[1].net_pnl == 5.0
    assert "06 2" in format_impulse_hour_rows(rows)


def trade(timestamp: datetime, pnl: float, realized_r: float) -> TradeCandidate:
    """Build a completed impulse trade."""

    return TradeCandidate(
        setup="impulse",
        entry_timestamp=timestamp,
        exit_timestamp=timestamp,
        side=1,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        risk_per_unit=10.0,
        pnl=pnl,
        realized_r=realized_r,
        exit_reason="time",
    )
