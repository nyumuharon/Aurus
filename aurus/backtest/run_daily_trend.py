"""Run the daily London trend strategy on real XAU/USD data."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig, BacktestResult
from aurus.data import IngestedMarketData, load_real_xauusd_5m_csv
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import DailyLondonTrendConfig, DailyLondonTrendStrategy, DailyTrendWindow


def current_daily_trend_config() -> DailyLondonTrendConfig:
    """Return the current daily-trading research configuration."""

    return DailyLondonTrendConfig(
        context_ema_period=20,
        context_atr_period=14,
        windows=(
            DailyTrendWindow(label="london_full", entry_hour_utc=7, exit_hour_utc=20),
        ),
        atr_stop_multiplier=Decimal("3"),
        reward_risk=Decimal("2.5"),
    )


def current_daily_trend_backtest_config() -> BacktestConfig:
    """Return static-stop execution assumptions for the daily trend strategy."""

    return BacktestConfig(record_events=False)


def run_daily_trend_backtest(
    *,
    data: IngestedMarketData,
    strategy_config: DailyLondonTrendConfig | None = None,
    backtest_config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run the daily trend strategy against already-ingested real bars."""

    strategy = DailyLondonTrendStrategy(
        context_bars=data.context_bars,
        config=strategy_config or current_daily_trend_config(),
    )
    return BacktestEngine(
        strategy=strategy,
        config=backtest_config or current_daily_trend_backtest_config(),
    ).run(data.execution_bars)


def format_daily_trend_summary(result: BacktestResult) -> str:
    """Render required metrics for daily trend checks."""

    metrics = calculate_metrics(result.trades, result.equity_curve)
    return "\n".join(
        [
            "Aurus daily London trend backtest summary",
            f"total trades: {metrics.trade_count}",
            f"win rate: {metrics.win_rate}",
            f"profit factor: {format_decimal(metrics.profit_factor)}",
            f"max drawdown: {metrics.max_drawdown}",
            f"net PnL: {metrics.total_pnl}",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run daily London trend on real XAU/USD CSV.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_real_xauusd_5m_csv(args.data)
    result = run_daily_trend_backtest(data=data)
    print(format_daily_trend_summary(result))


if __name__ == "__main__":
    main()
