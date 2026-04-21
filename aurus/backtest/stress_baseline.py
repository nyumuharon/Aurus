"""Execution-friction stress test for the current best baseline configuration."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.run_baseline import DEFAULT_LARGE_SAMPLE_DATA_PATH, ensure_large_sample_dataset
from aurus.backtest.types import BacktestConfig
from aurus.data import CsvBarLoader
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy

DEFAULT_STRESS_RESULTS_PATH = Path("artifacts/baseline-stress-test.csv")
STRESS_COLUMNS = (
    "scenario",
    "entry_slippage",
    "exit_slippage",
    "spread_multiplier",
    "total_trades",
    "win_rate",
    "profit_factor",
    "max_drawdown",
    "net_pnl",
)
BEST_BASELINE_CONFIG = BaselineStrategyConfig(
    confirmation_mode="relaxed",
    min_atr=Decimal("0.75"),
    max_spread=Decimal("0.50"),
    context_ema_period=3,
    execution_ema_period=3,
)


@dataclass(frozen=True)
class StressScenario:
    """Execution-only friction assumptions for one stress run."""

    name: str
    entry_slippage: Decimal
    exit_slippage: Decimal
    spread_multiplier: Decimal


@dataclass(frozen=True)
class StressResult:
    """Metrics for one stress scenario."""

    scenario: StressScenario
    total_trades: int
    win_rate: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    net_pnl: Decimal


STRESS_SCENARIOS = (
    StressScenario(
        name="normal",
        entry_slippage=Decimal("0"),
        exit_slippage=Decimal("0"),
        spread_multiplier=Decimal("1"),
    ),
    StressScenario(
        name="moderate stress",
        entry_slippage=Decimal("0.05"),
        exit_slippage=Decimal("0.05"),
        spread_multiplier=Decimal("1.5"),
    ),
    StressScenario(
        name="severe stress",
        entry_slippage=Decimal("0.15"),
        exit_slippage=Decimal("0.15"),
        spread_multiplier=Decimal("2.5"),
    ),
)


def run_stress_test(
    *,
    data_path: Path = DEFAULT_LARGE_SAMPLE_DATA_PATH,
    scenarios: tuple[StressScenario, ...] = STRESS_SCENARIOS,
) -> list[StressResult]:
    """Run the current best baseline config under execution-friction scenarios."""

    resolved_data_path = ensure_large_sample_dataset(data_path)
    loader = CsvBarLoader(resolved_data_path, default_instrument=BEST_BASELINE_CONFIG.instrument)
    execution_bars = loader.load_bars(
        instrument=BEST_BASELINE_CONFIG.instrument,
        timeframe=BEST_BASELINE_CONFIG.execution_timeframe,
    )
    context_bars = loader.load_bars(
        instrument=BEST_BASELINE_CONFIG.instrument,
        timeframe=BEST_BASELINE_CONFIG.context_timeframe,
    )

    results: list[StressResult] = []
    for scenario in scenarios:
        strategy = BaselineXauUsdStrategy(
            context_bars=context_bars,
            config=BEST_BASELINE_CONFIG,
        )
        backtest_config = BacktestConfig(
            entry_slippage=scenario.entry_slippage,
            exit_slippage=scenario.exit_slippage,
            spread_multiplier=scenario.spread_multiplier,
            record_events=False,
        )
        backtest_result = BacktestEngine(strategy=strategy, config=backtest_config).run(
            execution_bars
        )
        metrics = calculate_metrics(backtest_result.trades, backtest_result.equity_curve)
        results.append(
            StressResult(
                scenario=scenario,
                total_trades=metrics.trade_count,
                win_rate=metrics.win_rate,
                profit_factor=metrics.profit_factor,
                max_drawdown=metrics.max_drawdown,
                net_pnl=metrics.total_pnl,
            )
        )

    return results


def write_stress_results(path: Path, results: list[StressResult]) -> None:
    """Persist stress-test results as deterministic CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STRESS_COLUMNS)
        writer.writeheader()
        for result in results:
            writer.writerow(stress_result_row(result))


def stress_result_row(result: StressResult) -> dict[str, str]:
    """Convert one stress result to a CSV row."""

    return {
        "scenario": result.scenario.name,
        "entry_slippage": str(result.scenario.entry_slippage),
        "exit_slippage": str(result.scenario.exit_slippage),
        "spread_multiplier": str(result.scenario.spread_multiplier),
        "total_trades": str(result.total_trades),
        "win_rate": str(result.win_rate),
        "profit_factor": format_decimal(result.profit_factor),
        "max_drawdown": str(result.max_drawdown),
        "net_pnl": str(result.net_pnl),
    }


def format_stress_table(results: list[StressResult]) -> str:
    """Render the 3-row stress-test summary table."""

    lines = [
        (
            "scenario        entry_slip exit_slip spread_x trades win_rate "
            "profit_factor max_drawdown net_pnl"
        )
    ]
    for result in results:
        lines.append(
            f"{result.scenario.name:<15} {str(result.scenario.entry_slippage):>10} "
            f"{str(result.scenario.exit_slippage):>9} {str(result.scenario.spread_multiplier):>8} "
            f"{result.total_trades:>6} {str(result.win_rate):>8} "
            f"{format_decimal(result.profit_factor):>13} {str(result.max_drawdown):>12} "
            f"{str(result.net_pnl):>7}"
        )
    return "\n".join(lines)


def performance_collapses(results: list[StressResult]) -> bool:
    """Return True when severe friction removes positive expectancy on this sample."""

    severe = next(result for result in results if result.scenario.name == "severe stress")
    return severe.net_pnl <= Decimal("0") or (
        severe.profit_factor is not None and severe.profit_factor < Decimal("1")
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run baseline execution-friction stress tests.")
    parser.add_argument(
        "--data",
        default=DEFAULT_LARGE_SAMPLE_DATA_PATH,
        type=Path,
        help="Large-sample CSV path. Created deterministically if missing.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_STRESS_RESULTS_PATH,
        type=Path,
        help="Output CSV path for stress-test results.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    results = run_stress_test(data_path=args.data)
    write_stress_results(args.output, results)
    print("Baseline execution-friction stress test")
    print(format_stress_table(results))
    collapse_text = "yes" if performance_collapses(results) else "no"
    print(f"\nperformance collapses under severe friction: {collapse_text}")
    print(f"Saved stress-test results: {args.output}")


if __name__ == "__main__":
    main()
