"""Tests for active-hour daily trend analysis."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurus.backtest.analyze_daily_trend_hours import (
    ActiveHourResult,
    format_top_rows,
    parse_hour_list,
    realized_pnl_by_month,
    summarize_hour_result,
    write_active_hour_csv,
)
from aurus.backtest.types import BacktestResult, EquityPoint, TradeRecord


def test_realized_pnl_by_month_groups_closed_trades() -> None:
    result = BacktestResult(
        trades=(
            trade(datetime(2026, 1, 3, tzinfo=UTC), Decimal("10")),
            trade(datetime(2026, 1, 4, tzinfo=UTC), Decimal("-3")),
            trade(datetime(2026, 2, 1, tzinfo=UTC), Decimal("5")),
        ),
        equity_curve=(),
        event_log=(),
        events=(),
    )

    assert realized_pnl_by_month(result) == {
        "2026-01": Decimal("7"),
        "2026-02": Decimal("5"),
    }


def test_summarize_hour_result_reports_monthly_and_trade_metrics() -> None:
    result = BacktestResult(
        trades=(
            trade(datetime(2026, 1, 3, tzinfo=UTC), Decimal("10")),
            trade(datetime(2026, 2, 1, tzinfo=UTC), Decimal("-5")),
        ),
        equity_curve=(
            equity(datetime(2026, 1, 3, tzinfo=UTC), Decimal("100010")),
            equity(datetime(2026, 2, 1, tzinfo=UTC), Decimal("100005")),
        ),
        event_log=(),
        events=(),
    )

    row = summarize_hour_result(result=result, entry_hour=6, exit_hour=21)

    assert row.entry_hour_utc == 6
    assert row.exit_hour_utc == 21
    assert row.trades == 2
    assert row.net_pnl == Decimal("5")
    assert row.average_monthly_pnl == Decimal("2.5")
    assert row.worst_monthly_pnl == Decimal("-5")
    assert row.best_monthly_pnl == Decimal("10")
    assert row.positive_months == 1
    assert row.total_months == 2


def test_write_active_hour_csv_and_format_rows(tmp_path: Path) -> None:
    row = ActiveHourResult(
        entry_hour_utc=6,
        exit_hour_utc=21,
        trades=10,
        win_rate=Decimal("0.5"),
        profit_factor=Decimal("1.25"),
        max_drawdown=Decimal("20"),
        net_pnl=Decimal("100"),
        average_monthly_pnl=Decimal("10"),
        worst_monthly_pnl=Decimal("-5"),
        best_monthly_pnl=Decimal("30"),
        positive_months=2,
        total_months=3,
    )
    output = tmp_path / "hours.csv"

    write_active_hour_csv(output, [row])
    formatted = format_top_rows([row])

    assert output.read_text(encoding="utf-8").splitlines()[0].startswith("entry_hour_utc")
    assert "06 21 10 1.25 100 10 -5 20 2/3" in formatted


def test_parse_hour_list_validates_utc_hours() -> None:
    assert parse_hour_list("0, 6,21") == (0, 6, 21)


def trade(exit_timestamp: datetime, pnl: Decimal) -> TradeRecord:
    """Build a minimal trade record."""

    return TradeRecord(
        trade_id=f"trade-{exit_timestamp.isoformat()}",
        instrument="XAU/USD",
        side="buy",
        quantity=Decimal("1"),
        entry_timestamp=exit_timestamp,
        exit_timestamp=exit_timestamp,
        entry_price=Decimal("100"),
        exit_price=Decimal("100") + pnl,
        gross_pnl=pnl,
        commission=Decimal("0"),
        net_pnl=pnl,
        exit_reason="signal_exit",
    )


def equity(timestamp: datetime, value: Decimal) -> EquityPoint:
    """Build a minimal equity point."""

    return EquityPoint(
        timestamp=timestamp,
        cash=value,
        realized_pnl=value - Decimal("100000"),
        unrealized_pnl=Decimal("0"),
        equity=value,
    )
