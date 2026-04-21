"""Deterministic parameter sweep for the baseline XAU/USD strategy."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.run_baseline import (
    DEFAULT_LARGE_SAMPLE_DATA_PATH,
    ensure_large_sample_dataset,
)
from aurus.backtest.types import BacktestConfig
from aurus.data import CsvBarLoader
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy, ConfirmationMode

DEFAULT_SWEEP_RESULTS_PATH = Path("artifacts/baseline-parameter-sweep.csv")
SWEEP_COLUMNS = (
    "rank",
    "confirmation_mode",
    "min_atr",
    "max_spread",
    "context_ema_period",
    "execution_ema_period",
    "total_trades",
    "win_rate",
    "profit_factor",
    "max_drawdown",
    "net_pnl",
)


@dataclass(frozen=True)
class BaselineSweepGrid:
    """Explicit deterministic parameter grid."""

    confirmation_modes: tuple[ConfirmationMode, ...] = ("strict", "relaxed")
    min_atrs: tuple[Decimal, ...] = (Decimal("0.25"), Decimal("0.50"), Decimal("0.75"))
    max_spreads: tuple[Decimal, ...] = (Decimal("0.50"), Decimal("0.75"), Decimal("1.00"))
    context_ema_periods: tuple[int, ...] = (3, 5, 10)
    execution_ema_periods: tuple[int, ...] = (3, 5, 10)


@dataclass(frozen=True)
class BaselineSweepResult:
    """Metrics for one baseline parameter combination."""

    confirmation_mode: ConfirmationMode
    min_atr: Decimal
    max_spread: Decimal
    context_ema_period: int
    execution_ema_period: int
    total_trades: int
    win_rate: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    net_pnl: Decimal


def run_parameter_sweep(
    *,
    data_path: Path = DEFAULT_LARGE_SAMPLE_DATA_PATH,
    grid: BaselineSweepGrid | None = None,
    backtest_config: BacktestConfig | None = None,
) -> list[BaselineSweepResult]:
    """Run the deterministic baseline strategy parameter sweep."""

    resolved_data_path = ensure_large_sample_dataset(data_path)
    loader = CsvBarLoader(resolved_data_path, default_instrument="XAU/USD")
    execution_bars = loader.load_bars(instrument="XAU/USD", timeframe="5m")
    context_bars = loader.load_bars(instrument="XAU/USD", timeframe="1h")
    selected_grid = grid or BaselineSweepGrid()
    config = backtest_config or BacktestConfig(record_events=False)

    results: list[BaselineSweepResult] = []
    for confirmation_mode, min_atr, max_spread, context_period, execution_period in product(
        selected_grid.confirmation_modes,
        selected_grid.min_atrs,
        selected_grid.max_spreads,
        selected_grid.context_ema_periods,
        selected_grid.execution_ema_periods,
    ):
        strategy_config = BaselineStrategyConfig(
            context_ema_period=context_period,
            execution_ema_period=execution_period,
            atr_period=14,
            min_atr=min_atr,
            max_spread=max_spread,
            confirmation_mode=confirmation_mode,
        )
        strategy = BaselineXauUsdStrategy(context_bars=context_bars, config=strategy_config)
        backtest_result = BacktestEngine(strategy=strategy, config=config).run(execution_bars)
        metrics = calculate_metrics(backtest_result.trades, backtest_result.equity_curve)
        results.append(
            BaselineSweepResult(
                confirmation_mode=confirmation_mode,
                min_atr=min_atr,
                max_spread=max_spread,
                context_ema_period=context_period,
                execution_ema_period=execution_period,
                total_trades=metrics.trade_count,
                win_rate=metrics.win_rate,
                profit_factor=metrics.profit_factor,
                max_drawdown=metrics.max_drawdown,
                net_pnl=metrics.total_pnl,
            )
        )

    return rank_sweep_results(results)


def rank_sweep_results(results: list[BaselineSweepResult]) -> list[BaselineSweepResult]:
    """Rank by profit factor, then net PnL, with deterministic tie-breakers."""

    return sorted(
        results,
        key=lambda result: (
            _profit_factor_sort_key(result),
            result.net_pnl,
            result.total_trades,
            result.confirmation_mode,
            -result.context_ema_period,
            -result.execution_ema_period,
            -result.min_atr,
            -result.max_spread,
        ),
        reverse=True,
    )


def write_sweep_results(path: Path, results: list[BaselineSweepResult]) -> None:
    """Persist ranked sweep results as deterministic CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWEEP_COLUMNS)
        writer.writeheader()
        for rank, result in enumerate(results, start=1):
            writer.writerow(sweep_result_row(rank, result))


def sweep_result_row(rank: int, result: BaselineSweepResult) -> dict[str, str]:
    """Convert one sweep result to a CSV row."""

    return {
        "rank": str(rank),
        "confirmation_mode": result.confirmation_mode,
        "min_atr": str(result.min_atr),
        "max_spread": str(result.max_spread),
        "context_ema_period": str(result.context_ema_period),
        "execution_ema_period": str(result.execution_ema_period),
        "total_trades": str(result.total_trades),
        "win_rate": str(result.win_rate),
        "profit_factor": format_decimal(result.profit_factor),
        "max_drawdown": str(result.max_drawdown),
        "net_pnl": str(result.net_pnl),
    }


def format_ranked_table(results: list[BaselineSweepResult], *, limit: int = 10) -> str:
    """Render a compact ranked result table."""

    rows = [
        (
            rank,
            result.confirmation_mode,
            str(result.min_atr),
            str(result.max_spread),
            result.context_ema_period,
            result.execution_ema_period,
            result.total_trades,
            str(result.win_rate),
            format_decimal(result.profit_factor),
            str(result.max_drawdown),
            str(result.net_pnl),
        )
        for rank, result in enumerate(results[:limit], start=1)
    ]
    header = (
        "rank mode    min_atr max_spread ctx_ema exe_ema trades win_rate "
        "profit_factor max_drawdown net_pnl"
    )
    lines = [header]
    for row in rows:
        lines.append(
            f"{row[0]:>4} {row[1]:<7} {row[2]:>7} {row[3]:>10} "
            f"{row[4]:>7} {row[5]:>7} {row[6]:>6} {row[7]:>8} "
            f"{row[8]:>13} {row[9]:>12} {row[10]:>7}"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run the aurus baseline parameter sweep.")
    parser.add_argument(
        "--data",
        default=DEFAULT_LARGE_SAMPLE_DATA_PATH,
        type=Path,
        help="Large-sample CSV path. Created deterministically if missing.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_SWEEP_RESULTS_PATH,
        type=Path,
        help="Output CSV path for ranked sweep results.",
    )
    parser.add_argument("--top", default=10, type=int, help="Number of ranked rows to print.")
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    results = run_parameter_sweep(data_path=args.data)
    write_sweep_results(args.output, results)
    print("Top configurations by profit factor, then net PnL")
    print(format_ranked_table(results, limit=args.top))
    print(f"\nSaved sweep results: {args.output}")


def _profit_factor_sort_key(result: BaselineSweepResult) -> tuple[int, Decimal]:
    if result.profit_factor is not None:
        return (1, result.profit_factor)
    if result.total_trades > 0 and result.net_pnl > Decimal("0"):
        return (2, Decimal("0"))
    return (0, Decimal("0"))


if __name__ == "__main__":
    main()
