"""Tests for the daily trend backtest runner."""

from decimal import Decimal

from aurus.backtest.run_daily_trend import (
    current_daily_trend_backtest_config,
    current_daily_trend_config,
)


def test_current_daily_trend_config_uses_daily_research_defaults() -> None:
    config = current_daily_trend_config()
    backtest_config = current_daily_trend_backtest_config()

    assert config.context_ema_period == 20
    assert config.context_atr_period == 14
    assert config.entry_hour_utc == 7
    assert config.atr_stop_multiplier == Decimal("3")
    assert config.reward_risk == Decimal("1.5")
    assert backtest_config.stop_tightening_enabled is False
