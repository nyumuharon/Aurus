"""Tests for structural portfolio analysis helpers."""

from datetime import UTC, datetime
from decimal import Decimal

from aurus.backtest.analyze_structure_portfolio import (
    PortfolioTrade,
    combine_components,
    format_portfolio_summaries,
    monthly_pnl,
    summarize_portfolio,
)
from aurus.backtest.scan_structural_setups import TradeCandidate
from aurus.backtest.types import TradeRecord


def test_combine_components_sorts_by_exit_timestamp() -> None:
    daily = (
        trade_record(datetime(2026, 1, 3, tzinfo=UTC), Decimal("4")),
        trade_record(datetime(2026, 1, 1, tzinfo=UTC), Decimal("5")),
    )
    channel = [
        trade_candidate(datetime(2026, 1, 2, tzinfo=UTC), 3.0),
    ]

    combined = combine_components(daily_trades=daily, channel_trades=channel)

    assert [trade.pnl for trade in combined] == [5.0, 3.0, 4.0]
    assert [trade.source for trade in combined] == [
        "daily_trend",
        "channel_breakout",
        "daily_trend",
    ]


def test_summarize_portfolio_metrics() -> None:
    trades = [
        PortfolioTrade("a", "2026-01-01T00:00:00+00:00", 10.0),
        PortfolioTrade("a", "2026-01-02T00:00:00+00:00", -5.0),
        PortfolioTrade("b", "2026-02-01T00:00:00+00:00", 4.0),
    ]

    summary = summarize_portfolio("test", trades)

    assert monthly_pnl(trades) == {"2026-01": 5.0, "2026-02": 4.0}
    assert summary.trades == 3
    assert summary.profit_factor == 2.8
    assert summary.net_pnl == 9.0
    assert summary.average_monthly_pnl == 4.5
    assert summary.positive_months == 2
    assert "test 3 2.8 9 4.5" in format_portfolio_summaries([summary])


def trade_record(exit_timestamp: datetime, pnl: Decimal) -> TradeRecord:
    """Build a minimal backtest trade record."""

    return TradeRecord(
        trade_id=exit_timestamp.isoformat(),
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
        exit_reason="test",
    )


def trade_candidate(exit_timestamp: datetime, pnl: float) -> TradeCandidate:
    """Build a completed research trade candidate."""

    return TradeCandidate(
        setup="test",
        entry_timestamp=exit_timestamp,
        exit_timestamp=exit_timestamp,
        side=1,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        risk_per_unit=2.0,
        pnl=pnl,
        realized_r=pnl / 2.0,
        exit_reason="test",
    )
