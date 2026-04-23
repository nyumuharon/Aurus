"""Tests for the daily trend backtest runner."""

from datetime import UTC, datetime
from decimal import Decimal

from aurus.backtest.run_daily_trend import (
    current_daily_trend_backtest_config,
    current_daily_trend_config,
    format_daily_trend_summary,
    format_monthly_pnl,
    format_yearly_pnl,
)
from aurus.backtest.types import BacktestResult, TradeRecord


def test_current_daily_trend_config_uses_daily_research_defaults() -> None:
    config = current_daily_trend_config()
    backtest_config = current_daily_trend_backtest_config()

    assert config.context_ema_period == 20
    assert config.context_atr_period == 14
    assert tuple(window.label for window in config.windows) == ("pre_london_full",)
    assert config.windows[0].entry_hour_utc == 6
    assert config.windows[0].exit_hour_utc == 21
    assert config.atr_stop_multiplier == Decimal("3")
    assert config.reward_risk == Decimal("3")
    assert config.quantity == Decimal("1")
    assert backtest_config.stop_tightening_enabled is False


def test_current_daily_trend_config_accepts_quantity_override() -> None:
    config = current_daily_trend_config(quantity=Decimal("2.5"))

    assert config.quantity == Decimal("2.5")


def test_daily_trend_summary_includes_yearly_and_latest_year_monthly_output() -> None:
    result = BacktestResult(
        trades=(
            trade(datetime(2025, 12, 31, tzinfo=UTC), Decimal("25")),
            trade(datetime(2026, 1, 31, tzinfo=UTC), Decimal("10")),
            trade(datetime(2026, 2, 28, tzinfo=UTC), Decimal("-4")),
        ),
        equity_curve=(),
        event_log=(),
        events=(),
    )

    summary = format_daily_trend_summary(result, starting_equity=Decimal("10000"))

    assert "starting equity: 10000" in summary
    assert "net return: 0.3100%" in summary
    assert "yearly PnL:" in summary
    assert "2025: PnL 25, return 0.2500%, ending equity 10025" in summary
    assert "2026: PnL 6, return 0.0600%, ending equity 10031" in summary
    assert "2026 monthly PnL:" in summary
    assert "2026-01: PnL 10, return 0.100%" in summary
    assert "2026-02: PnL -4, return -0.0400%" in summary


def test_daily_trend_pnl_formatters_handle_empty_results() -> None:
    assert format_yearly_pnl({}, starting_equity=Decimal("10000")) == ["none"]
    assert format_monthly_pnl({}) == ["none"]


def trade(exit_timestamp: datetime, pnl: Decimal) -> TradeRecord:
    """Build a minimal closed trade for summary formatting tests."""

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
