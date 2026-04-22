"""Run the baseline strategy on real historical XAU/USD 5-minute CSV data."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig, BacktestResult
from aurus.data import IngestedMarketData, TradingSession, load_real_xauusd_5m_csv
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy


def current_best_real_config() -> BaselineStrategyConfig:
    """Return the current best deterministic baseline config for external data checks."""

    return BaselineStrategyConfig(
        reward_risk=Decimal("1.10"),
        confirmation_mode="relaxed",
        min_atr=Decimal("0.75"),
        min_atr_strength=Decimal("0.0005"),
        min_trend_strength=Decimal("0.0002"),
        min_pre_entry_extension_atr=Decimal("0.645"),
        max_spread_to_risk=Decimal("0.055"),
        max_spread=Decimal("0.50"),
        context_ema_period=3,
        execution_ema_period=5,
        allowed_sessions=frozenset({TradingSession.LONDON.value}),
        allowed_london_subwindows=frozenset({"open", "mid"}),
    )


def current_best_real_backtest_config() -> BacktestConfig:
    """Return the current deterministic execution assumptions for real-data checks."""

    return BacktestConfig(
        record_events=False,
        stop_tightening_enabled=True,
        breakeven_trigger_r=Decimal("0.25"),
        breakeven_stop_r=Decimal("0.20"),
        trailing_trigger_r=Decimal("0.75"),
        trailing_stop_r=Decimal("0.50"),
    )


def run_real_baseline_backtest(
    *,
    data: IngestedMarketData,
    strategy_config: BaselineStrategyConfig | None = None,
    backtest_config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run the baseline strategy against already-ingested real bars."""

    config = strategy_config or current_best_real_config()
    strategy = BaselineXauUsdStrategy(context_bars=data.context_bars, config=config)
    return BacktestEngine(
        strategy=strategy,
        config=backtest_config or current_best_real_backtest_config(),
    ).run(data.execution_bars)


def format_real_baseline_summary(result: BacktestResult) -> str:
    """Render required metrics for real-data baseline checks."""

    metrics = calculate_metrics(result.trades, result.equity_curve)
    return "\n".join(
        [
            "Aurus real-data baseline backtest summary",
            f"total trades: {metrics.trade_count}",
            f"win rate: {metrics.win_rate}",
            f"profit factor: {format_decimal(metrics.profit_factor)}",
            f"max drawdown: {metrics.max_drawdown}",
            f"net PnL: {metrics.total_pnl}",
        ]
    )


def format_ingestion_report(data: IngestedMarketData) -> str:
    """Render deterministic ingestion quality details."""

    report = data.report
    return "\n".join(
        [
            "Real CSV ingestion report",
            f"source: {report.source_path}",
            f"input rows: {report.input_rows}",
            f"5m bars after duplicate removal: {report.output_bars}",
            f"duplicates removed: {report.duplicates_removed}",
            f"missing gap count: {len(report.missing_gaps)}",
            f"missing 5m bar count: {report.missing_bar_count}",
            f"derived closed 1h bars: {len(data.context_bars)}",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run baseline backtest on real XAU/USD CSV data.")
    parser.add_argument(
        "--data",
        required=True,
        type=Path,
        help=(
            "Real 5-minute CSV path. Format: timestamp,open,high,low,close,volume,"
            "spread(optional). Timestamps must be timezone-aware or Z-suffixed UTC."
        ),
    )
    parser.add_argument(
        "--fallback-spread",
        default=None,
        help="Optional spread to use when the CSV omits or leaves spread blank.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    fallback_spread = Decimal(args.fallback_spread) if args.fallback_spread is not None else None
    data = load_real_xauusd_5m_csv(args.data, fallback_spread=fallback_spread)
    result = run_real_baseline_backtest(data=data)
    print(format_ingestion_report(data))
    print()
    print(format_real_baseline_summary(result))


if __name__ == "__main__":
    main()
