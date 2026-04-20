"""Runnable baseline strategy backtest entry point."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig, BacktestResult
from aurus.data import CsvBarLoader
from aurus.ops import CsvTradeLedgerRepository, EventJournal, summarize_run
from aurus.ops.ledger import TRADE_LEDGER_COLUMNS
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy


@dataclass(frozen=True)
class BaselineBacktestRunConfig:
    """Typed configuration for the runnable baseline backtest."""

    data_path: Path
    trade_ledger_path: Path
    event_log_path: Path
    strategy: BaselineStrategyConfig
    backtest: BacktestConfig


def run_baseline_backtest(config: BaselineBacktestRunConfig) -> BacktestResult:
    """Load CSV bars, run the baseline strategy, and write artifacts."""

    loader = CsvBarLoader(config.data_path, default_instrument=config.strategy.instrument)
    execution_bars = loader.load_bars(
        instrument=config.strategy.instrument,
        timeframe=config.strategy.execution_timeframe,
    )
    context_bars = loader.load_bars(
        instrument=config.strategy.instrument,
        timeframe=config.strategy.context_timeframe,
    )
    strategy = BaselineXauUsdStrategy(context_bars=context_bars, config=config.strategy)
    result = BacktestEngine(strategy=strategy, config=config.backtest).run(execution_bars)

    write_trade_ledger(config.trade_ledger_path, result)
    EventJournal(config.event_log_path).append_many(result.events)
    return result


def write_trade_ledger(path: Path, result: BacktestResult) -> None:
    """Write the trade ledger artifact, including an empty header-only file."""

    repository = CsvTradeLedgerRepository(path)
    if result.trades:
        repository.append_many(result.trades)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(TRADE_LEDGER_COLUMNS) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run the aurus baseline XAU/USD backtest.")
    parser.add_argument(
        "--data",
        required=True,
        type=Path,
        help="CSV path containing 1H and 5M bars.",
    )
    parser.add_argument("--ledger", required=True, type=Path, help="Output CSV trade ledger path.")
    parser.add_argument("--events", required=True, type=Path, help="Output JSONL event log path.")
    parser.add_argument("--initial-cash", default="100000", help="Initial cash for the backtest.")
    parser.add_argument("--quantity", default="1", help="Default signal/order quantity.")
    parser.add_argument("--spread", default="0", help="Fallback simulated spread.")
    parser.add_argument("--slippage", default="0", help="Simulated slippage per fill.")
    parser.add_argument("--context-ema-period", default=50, type=int, help="1H EMA trend period.")
    parser.add_argument(
        "--execution-ema-period",
        default=20,
        type=int,
        help="5M EMA pullback period.",
    )
    parser.add_argument("--atr-period", default=14, type=int, help="5M ATR period.")
    parser.add_argument("--min-atr", default="1.0", help="Minimum 5M ATR threshold.")
    parser.add_argument("--max-spread", default="0.50", help="Maximum accepted bar spread.")
    parser.add_argument(
        "--atr-stop-floor-multiplier",
        default="1",
        help="Minimum stop distance as ATR multiple.",
    )
    parser.add_argument("--reward-risk", default="2", help="Fixed target reward/risk multiple.")
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> BaselineBacktestRunConfig:
    """Build typed run configuration from CLI args."""

    strategy_config = BaselineStrategyConfig(
        context_ema_period=args.context_ema_period,
        execution_ema_period=args.execution_ema_period,
        atr_period=args.atr_period,
        min_atr=Decimal(args.min_atr),
        max_spread=Decimal(args.max_spread),
        atr_stop_floor_multiplier=Decimal(args.atr_stop_floor_multiplier),
        reward_risk=Decimal(args.reward_risk),
        quantity=Decimal(args.quantity),
    )
    backtest_config = BacktestConfig(
        initial_cash=Decimal(args.initial_cash),
        default_quantity=Decimal(args.quantity),
        spread=Decimal(args.spread),
        slippage=Decimal(args.slippage),
    )
    return BaselineBacktestRunConfig(
        data_path=args.data,
        trade_ledger_path=args.ledger,
        event_log_path=args.events,
        strategy=strategy_config,
        backtest=backtest_config,
    )


def main() -> None:
    """CLI entry point."""

    result = run_baseline_backtest(config_from_args(parse_args()))
    print(summarize_run(result))


if __name__ == "__main__":
    main()
