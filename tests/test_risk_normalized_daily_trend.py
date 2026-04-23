"""Tests for risk-normalized daily trend reporting."""

from decimal import Decimal

from aurus.backtest.risk_normalized_daily_trend import (
    RTrade,
    format_risk_rows,
    simulate_risk_normalized_returns,
)


def test_simulate_risk_normalized_returns_applies_percent_risk() -> None:
    rows = (
        RTrade(exit_month="2026-01", realized_r=Decimal("1")),
        RTrade(exit_month="2026-01", realized_r=Decimal("-0.5")),
        RTrade(exit_month="2026-02", realized_r=Decimal("2")),
    )

    result = simulate_risk_normalized_returns(
        rows,
        starting_equity=Decimal("10000"),
        risk_pct=Decimal("0.02"),
    )

    assert result.ending_equity == Decimal("10501.9200000")
    assert result.positive_months == 2
    assert result.total_months == 2
    assert result.months_at_or_above_10pct == 0
    assert "0.02" in format_risk_rows((result,))
