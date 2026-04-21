"""Runnable baseline strategy backtest entry point."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig, BacktestResult
from aurus.data import CsvBarLoader
from aurus.ops.ledger import TRADE_LEDGER_COLUMNS, trade_to_row
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import (
    BaselineDiagnostics,
    BaselineStrategyConfig,
    BaselineXauUsdStrategy,
    ConfirmationMode,
)

DEFAULT_SAMPLE_DATA_PATH = Path("examples/baseline_sample_bars.csv")
DEFAULT_LARGE_SAMPLE_DATA_PATH = Path("examples/baseline_large_sample.csv")
DEFAULT_TRADE_LEDGER_PATH = Path("artifacts/baseline-trades.csv")
DEFAULT_EVENT_LOG_PATH = Path("artifacts/baseline-events.jsonl")
LARGE_SAMPLE_5M_BAR_COUNT = 2880
CSV_HEADER = "timestamp,instrument,timeframe,open,high,low,close,volume,spread"
SAMPLE_DATASET_LINES = (
    CSV_HEADER,
    "2026-04-21T00:00:00+00:00,XAU/USD,1h,2400.0,2400.5,2399.5,2400.0,100,0.20",
    "2026-04-21T01:00:00+00:00,XAU/USD,1h,2401.0,2401.5,2400.5,2401.0,100,0.20",
    "2026-04-21T02:00:00+00:00,XAU/USD,1h,2402.0,2402.5,2401.5,2402.0,100,0.20",
    "2026-04-21T03:00:00+00:00,XAU/USD,1h,2403.0,2403.5,2402.5,2403.0,100,0.20",
    "2026-04-21T04:00:00+00:00,XAU/USD,1h,2404.0,2404.5,2403.5,2404.0,100,0.20",
    "2026-04-21T05:00:00+00:00,XAU/USD,1h,2405.0,2405.5,2404.5,2405.0,100,0.20",
    "2026-04-21T06:00:00+00:00,XAU/USD,1h,2406.0,2406.5,2405.5,2406.0,100,0.20",
    "2026-04-21T07:00:00+00:00,XAU/USD,1h,2407.0,2407.5,2406.5,2407.0,100,0.20",
    "2026-04-21T07:00:00+00:00,XAU/USD,5m,2400.0,2400.4,2399.6,2400.0,10,0.20",
    "2026-04-21T07:05:00+00:00,XAU/USD,5m,2401.0,2401.4,2400.6,2401.0,10,0.20",
    "2026-04-21T07:10:00+00:00,XAU/USD,5m,2402.0,2402.4,2401.6,2402.0,10,0.20",
    "2026-04-21T07:15:00+00:00,XAU/USD,5m,2403.0,2403.4,2402.6,2403.0,10,0.20",
    "2026-04-21T07:20:00+00:00,XAU/USD,5m,2404.0,2404.4,2403.6,2404.0,10,0.20",
    "2026-04-21T07:25:00+00:00,XAU/USD,5m,2403.8,2404.2,2402.5,2403.0,10,0.20",
    "2026-04-21T07:30:00+00:00,XAU/USD,5m,2403.1,2405.2,2403.0,2404.8,10,0.20",
    "2026-04-21T07:35:00+00:00,XAU/USD,5m,2404.8,2410.0,2404.5,2409.5,10,0.20",
)


@dataclass(frozen=True)
class BaselineBacktestRunConfig:
    """Typed configuration for the runnable baseline backtest."""

    data_path: Path
    trade_ledger_path: Path
    event_log_path: Path
    strategy: BaselineStrategyConfig
    backtest: BacktestConfig
    diagnostics: BaselineDiagnostics | None = None
    diagnostics_path: Path | None = None


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
    strategy = BaselineXauUsdStrategy(
        context_bars=context_bars,
        config=config.strategy,
        diagnostics=config.diagnostics,
    )
    result = BacktestEngine(strategy=strategy, config=config.backtest).run(execution_bars)

    write_trade_ledger(config.trade_ledger_path, result)
    write_event_log(config.event_log_path, result)
    if config.diagnostics is not None and config.diagnostics_path is not None:
        config.diagnostics.write_summary(config.diagnostics_path)
    return result


def ensure_sample_dataset(path: Path = DEFAULT_SAMPLE_DATA_PATH) -> Path:
    """Return an existing sample dataset or create a deterministic one."""

    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(SAMPLE_DATASET_LINES) + "\n", encoding="utf-8")
    return path


def ensure_large_sample_dataset(path: Path = DEFAULT_LARGE_SAMPLE_DATA_PATH) -> Path:
    """Return an existing large sample dataset or create a deterministic one."""

    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_large_sample_csv(), encoding="utf-8")
    return path


def _large_sample_csv(bar_count: int = LARGE_SAMPLE_5M_BAR_COUNT) -> str:
    """Generate deterministic 5M and closed 1H XAU/USD bars."""

    five_minute_rows = _large_sample_five_minute_rows(bar_count)
    hourly_rows = _large_sample_hourly_rows(five_minute_rows)
    rows = [CSV_HEADER, *hourly_rows, *five_minute_rows]
    return "\n".join(rows) + "\n"


def _large_sample_five_minute_rows(bar_count: int) -> list[str]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    previous_close = Decimal("2400.00")
    rows: list[str] = []

    for index in range(bar_count):
        timestamp = start + timedelta(minutes=5 * index)
        drift, base_range, volume_base, spread_base = _large_sample_regime(index)
        cycle = Decimal((index % 24) - 12) / Decimal("100")
        micro_cycle = Decimal((index % 7) - 3) / Decimal("100")
        open_price = previous_close
        close_price = open_price + drift + cycle + micro_cycle
        range_padding = base_range + abs(cycle) + (Decimal(index % 5) / Decimal("100"))
        high = max(open_price, close_price) + range_padding
        low = min(open_price, close_price) - range_padding
        volume = volume_base + Decimal((index % 17) * 4)
        spread = spread_base + Decimal(index % 9) / Decimal("100")

        rows.append(
            _bar_csv_row(
                timestamp=timestamp,
                timeframe="5m",
                open_price=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=volume,
                spread=spread,
            )
        )
        previous_close = close_price

    return rows


def _large_sample_regime(index: int) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if index < 576:
        return Decimal("0.035"), Decimal("0.22"), Decimal("85"), Decimal("0.18")
    if index < 1152:
        return Decimal("0.000"), Decimal("0.55"), Decimal("150"), Decimal("0.27")
    if index < 1728:
        return Decimal("-0.045"), Decimal("0.62"), Decimal("180"), Decimal("0.34")
    if index < 2304:
        return Decimal("0.055"), Decimal("0.48"), Decimal("165"), Decimal("0.24")
    return Decimal("-0.005"), Decimal("0.25"), Decimal("95"), Decimal("0.20")


def _large_sample_hourly_rows(five_minute_rows: list[str]) -> list[str]:
    hourly_rows: list[str] = []
    for offset in range(0, len(five_minute_rows), 12):
        hour_rows = five_minute_rows[offset : offset + 12]
        if len(hour_rows) < 12:
            break

        parsed = [row.split(",") for row in hour_rows]
        timestamp = datetime.fromisoformat(parsed[0][0])
        open_price = Decimal(parsed[0][3])
        high = max(Decimal(row[4]) for row in parsed)
        low = min(Decimal(row[5]) for row in parsed)
        close = Decimal(parsed[-1][6])
        volume = sum((Decimal(row[7]) for row in parsed), start=Decimal("0"))
        spread = sum((Decimal(row[8]) for row in parsed), start=Decimal("0")) / Decimal(
            len(parsed)
        )
        hourly_rows.append(
            _bar_csv_row(
                timestamp=timestamp,
                timeframe="1h",
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                spread=spread,
            )
        )
    return hourly_rows


def _bar_csv_row(
    *,
    timestamp: datetime,
    timeframe: str,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: Decimal,
    spread: Decimal,
) -> str:
    return ",".join(
        [
            timestamp.isoformat(),
            "XAU/USD",
            timeframe,
            _format_price(open_price),
            _format_price(high),
            _format_price(low),
            _format_price(close),
            _format_volume(volume),
            _format_spread(spread),
        ]
    )


def _format_price(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _format_volume(value: Decimal) -> str:
    return str(value.quantize(Decimal("1")))


def _format_spread(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def write_trade_ledger(path: Path, result: BacktestResult) -> None:
    """Write a deterministic trade ledger artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRADE_LEDGER_COLUMNS)
        writer.writeheader()
        for trade in result.trades:
            writer.writerow(trade_to_row(trade))


def write_event_log(path: Path, result: BacktestResult) -> None:
    """Write a deterministic JSONL event log artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(result.event_log)
    path.write_text(f"{payload}\n" if payload else "", encoding="utf-8")


def format_baseline_summary(result: BacktestResult) -> str:
    """Render the required baseline backtest summary fields."""

    metrics = calculate_metrics(result.trades, result.equity_curve)
    return "\n".join(
        [
            "Aurus baseline backtest summary",
            f"total trades: {metrics.trade_count}",
            f"win rate: {metrics.win_rate}",
            f"profit factor: {format_decimal(metrics.profit_factor)}",
            f"max drawdown: {metrics.max_drawdown}",
            f"net PnL: {metrics.total_pnl}",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run the aurus baseline XAU/USD backtest.")
    parser.add_argument(
        "--data",
        default=None,
        type=Path,
        help=(
            "CSV path containing 1H and 5M bars. Defaults to "
            "examples/baseline_sample_bars.csv unless --large-sample is set."
        ),
    )
    parser.add_argument(
        "--large-sample",
        action="store_true",
        help="Use examples/baseline_large_sample.csv, creating it deterministically if missing.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print a baseline strategy rejection funnel after the run.",
    )
    parser.add_argument(
        "--diagnostics-file",
        default=None,
        type=Path,
        help="Optional path for writing the diagnostic rejection funnel.",
    )
    parser.add_argument(
        "--ledger",
        default=DEFAULT_TRADE_LEDGER_PATH,
        type=Path,
        help="Output CSV trade ledger path.",
    )
    parser.add_argument(
        "--events",
        default=DEFAULT_EVENT_LOG_PATH,
        type=Path,
        help="Output JSONL event log path.",
    )
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
    parser.add_argument(
        "--confirmation-mode",
        choices=("strict", "relaxed"),
        default="strict",
        help="Confirmation candle rule. strict preserves the original breakout rule.",
    )
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
        confirmation_mode=_confirmation_mode(args.confirmation_mode),
        quantity=Decimal(args.quantity),
    )
    backtest_config = BacktestConfig(
        initial_cash=Decimal(args.initial_cash),
        default_quantity=Decimal(args.quantity),
        spread=Decimal(args.spread),
        slippage=Decimal(args.slippage),
    )
    data_path = _resolve_data_path(args.data, use_large_sample=args.large_sample)
    return BaselineBacktestRunConfig(
        data_path=data_path,
        trade_ledger_path=args.ledger,
        event_log_path=args.events,
        strategy=strategy_config,
        backtest=backtest_config,
        diagnostics=BaselineDiagnostics() if args.diagnostics else None,
        diagnostics_path=args.diagnostics_file,
    )


def _resolve_data_path(data: Path | None, *, use_large_sample: bool) -> Path:
    if data is not None:
        return data
    if use_large_sample:
        return ensure_large_sample_dataset()
    return ensure_sample_dataset()


def _confirmation_mode(value: str) -> ConfirmationMode:
    if value == "strict":
        return "strict"
    if value == "relaxed":
        return "relaxed"
    raise ValueError(f"unsupported confirmation mode: {value}")


def main() -> None:
    """CLI entry point."""

    config = config_from_args(parse_args())
    result = run_baseline_backtest(config)
    print(format_baseline_summary(result))
    if config.diagnostics is not None:
        print()
        print(config.diagnostics.format_summary())


if __name__ == "__main__":
    main()
