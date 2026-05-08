"""Tests for risk-normalized structural portfolio reporting."""

from datetime import UTC, datetime
from decimal import Decimal

from aurus.backtest.risk_normalized_structure_portfolio import (
    PortfolioRTrade,
    combine_portfolio_r_trades,
    format_monthly_returns,
    simulate_portfolio_risk_normalized_returns,
)


def test_combine_portfolio_r_trades_sorts_by_exit_timestamp() -> None:
    daily = (
        PortfolioRTrade("daily", datetime(2026, 1, 3, tzinfo=UTC), Decimal("1")),
        PortfolioRTrade("daily", datetime(2026, 1, 1, tzinfo=UTC), Decimal("1")),
    )
    channel = (PortfolioRTrade("channel", datetime(2026, 1, 2, tzinfo=UTC), Decimal("-0.5")),)
    impulse = (PortfolioRTrade("impulse", datetime(2026, 1, 4, tzinfo=UTC), Decimal("0.25")),)
    reversal = (PortfolioRTrade("reversal", datetime(2026, 1, 5, tzinfo=UTC), Decimal("-0.25")),)

    combined = combine_portfolio_r_trades(
        daily_trades=daily,
        channel_trades=channel,
        impulse_trades=impulse,
        reversal_trades=reversal,
    )

    assert [trade.source for trade in combined] == [
        "daily",
        "channel",
        "daily",
        "impulse",
        "reversal",
    ]


def test_simulate_portfolio_risk_normalized_returns() -> None:
    trades = (
        PortfolioRTrade("daily", datetime(2026, 1, 1, tzinfo=UTC), Decimal("1")),
        PortfolioRTrade("channel", datetime(2026, 1, 2, tzinfo=UTC), Decimal("-0.5")),
        PortfolioRTrade("daily", datetime(2026, 2, 1, tzinfo=UTC), Decimal("2")),
    )

    result, monthly = simulate_portfolio_risk_normalized_returns(
        trades,
        starting_equity=Decimal("10000"),
        risk_pct=Decimal("0.02"),
    )

    assert result.ending_equity == Decimal("10501.9200000")
    assert monthly == {
        "2026-01": Decimal("98.000000"),
        "2026-02": Decimal("403.9200000"),
    }
    assert result.months_at_or_above_10pct == 0
    assert "2026-01" in format_monthly_returns(monthly, starting_equity=Decimal("10000"))
