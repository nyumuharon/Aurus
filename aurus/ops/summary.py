"""Run summary rendering."""

from __future__ import annotations

from decimal import Decimal

from aurus.backtest.types import BacktestResult
from aurus.ops.metrics import PerformanceMetrics, calculate_metrics


def format_decimal(value: Decimal | None) -> str:
    """Format optional decimals for human-readable summaries."""

    return "n/a" if value is None else str(value)


def summarize_run(result: BacktestResult) -> str:
    """Render a simple text summary for a completed run."""

    metrics = calculate_metrics(result.trades, result.equity_curve)
    return summarize_metrics(metrics)


def summarize_metrics(metrics: PerformanceMetrics) -> str:
    """Render a simple text summary from metrics."""

    return "\n".join(
        [
            "Aurus run summary",
            f"trades: {metrics.trade_count}",
            f"total_pnl: {metrics.total_pnl}",
            f"max_drawdown: {metrics.max_drawdown}",
            f"win_rate: {metrics.win_rate}",
            f"profit_factor: {format_decimal(metrics.profit_factor)}",
            f"winning_trades: {metrics.winning_trades}",
            f"losing_trades: {metrics.losing_trades}",
        ]
    )

