"""Analyze active UTC hours for the daily trend structure."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from aurus.backtest.run_daily_trend import run_daily_trend_backtest
from aurus.backtest.types import BacktestResult
from aurus.data import IngestedMarketData, load_real_xauusd_5m_csv
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import DailyLondonTrendConfig, DailyTrendWindow


@dataclass(frozen=True)
class ActiveHourResult:
    """Metrics for one entry/exit hour combination."""

    entry_hour_utc: int
    exit_hour_utc: int
    trades: int
    win_rate: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    net_pnl: Decimal
    average_monthly_pnl: Decimal
    worst_monthly_pnl: Decimal
    best_monthly_pnl: Decimal
    positive_months: int
    total_months: int


def analyze_active_hours(
    *,
    data: IngestedMarketData,
    entry_hours: tuple[int, ...] = (0, 3, 5, 6, 7, 8, 10, 12, 13, 15),
    exit_hours: tuple[int, ...] = (10, 12, 15, 17, 19, 21, 22),
    min_hold_hours: int = 4,
    reward_risk: Decimal = Decimal("3"),
    atr_stop_multiplier: Decimal = Decimal("3"),
) -> list[ActiveHourResult]:
    """Run deterministic entry/exit hour checks for the daily trend structure."""

    results: list[ActiveHourResult] = []
    for entry_hour in entry_hours:
        for exit_hour in exit_hours:
            if exit_hour <= entry_hour + min_hold_hours:
                continue
            config = DailyLondonTrendConfig(
                context_ema_period=20,
                context_atr_period=14,
                windows=(
                    DailyTrendWindow(
                        label=f"hour_{entry_hour:02d}_{exit_hour:02d}",
                        entry_hour_utc=entry_hour,
                        exit_hour_utc=exit_hour,
                    ),
                ),
                atr_stop_multiplier=atr_stop_multiplier,
                reward_risk=reward_risk,
            )
            results.append(
                summarize_hour_result(
                    result=run_daily_trend_backtest(data=data, strategy_config=config),
                    entry_hour=entry_hour,
                    exit_hour=exit_hour,
                )
            )
    return sorted(results, key=lambda row: (row.profit_factor, row.net_pnl), reverse=True)


def summarize_hour_result(
    *,
    result: BacktestResult,
    entry_hour: int,
    exit_hour: int,
) -> ActiveHourResult:
    """Summarize one backtest result for active-hour comparison."""

    metrics = calculate_metrics(result.trades, result.equity_curve)
    monthly_pnl = realized_pnl_by_month(result)
    monthly_values = tuple(monthly_pnl.values())
    total_months = len(monthly_values)
    average_monthly_pnl = (
        sum(monthly_values, Decimal("0")) / Decimal(total_months) if total_months else Decimal("0")
    )
    return ActiveHourResult(
        entry_hour_utc=entry_hour,
        exit_hour_utc=exit_hour,
        trades=metrics.trade_count,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor or Decimal("0"),
        max_drawdown=metrics.max_drawdown,
        net_pnl=metrics.total_pnl,
        average_monthly_pnl=average_monthly_pnl,
        worst_monthly_pnl=min(monthly_values) if monthly_values else Decimal("0"),
        best_monthly_pnl=max(monthly_values) if monthly_values else Decimal("0"),
        positive_months=sum(value > Decimal("0") for value in monthly_values),
        total_months=total_months,
    )


def realized_pnl_by_month(result: BacktestResult) -> dict[str, Decimal]:
    """Group realized PnL by exit month."""

    monthly_pnl: defaultdict[str, Decimal] = defaultdict(Decimal)
    for trade in result.trades:
        month = f"{trade.exit_timestamp.year}-{trade.exit_timestamp.month:02d}"
        monthly_pnl[month] += trade.net_pnl
    return dict(sorted(monthly_pnl.items()))


def write_active_hour_csv(path: Path, rows: list[ActiveHourResult]) -> None:
    """Write active-hour analysis rows to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "entry_hour_utc",
                "exit_hour_utc",
                "trades",
                "win_rate",
                "profit_factor",
                "max_drawdown",
                "net_pnl",
                "average_monthly_pnl",
                "worst_monthly_pnl",
                "best_monthly_pnl",
                "positive_months",
                "total_months",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.entry_hour_utc,
                    row.exit_hour_utc,
                    row.trades,
                    row.win_rate,
                    row.profit_factor,
                    row.max_drawdown,
                    row.net_pnl,
                    row.average_monthly_pnl,
                    row.worst_monthly_pnl,
                    row.best_monthly_pnl,
                    row.positive_months,
                    row.total_months,
                ]
            )


def format_top_rows(rows: list[ActiveHourResult], *, limit: int = 10) -> str:
    """Render the top active-hour rows."""

    lines = [
        "entry exit trades PF net_pnl avg_month worst_month max_dd pos_months",
    ]
    for row in rows[:limit]:
        lines.append(
            " ".join(
                [
                    f"{row.entry_hour_utc:02d}",
                    f"{row.exit_hour_utc:02d}",
                    str(row.trades),
                    format_decimal(row.profit_factor),
                    str(row.net_pnl),
                    str(row.average_monthly_pnl),
                    str(row.worst_monthly_pnl),
                    str(row.max_drawdown),
                    f"{row.positive_months}/{row.total_months}",
                ]
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Analyze active UTC hours for XAU/USD.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/daily-trend-active-hours.csv"),
        type=Path,
        help="CSV output path.",
    )
    parser.add_argument("--top", default=10, type=int, help="Rows to print.")
    parser.add_argument(
        "--entry-hours",
        default="0,3,5,6,7,8,10,12,13,15",
        help="Comma-separated UTC entry hours to scan.",
    )
    parser.add_argument(
        "--exit-hours",
        default="10,12,15,17,19,21,22",
        help="Comma-separated UTC exit hours to scan.",
    )
    return parser.parse_args()


def parse_hour_list(raw_value: str) -> tuple[int, ...]:
    """Parse a comma-separated list of UTC hours."""

    hours = tuple(int(value.strip()) for value in raw_value.split(",") if value.strip())
    invalid = [hour for hour in hours if hour < 0 or hour > 23]
    if invalid:
        raise ValueError(f"UTC hours must be between 0 and 23: {invalid}")
    return hours


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_real_xauusd_5m_csv(args.data)
    rows = analyze_active_hours(
        data=data,
        entry_hours=parse_hour_list(args.entry_hours),
        exit_hours=parse_hour_list(args.exit_hours),
    )
    write_active_hour_csv(args.output, rows)
    print(format_top_rows(rows, limit=args.top))
    print(f"saved active-hour analysis: {args.output}")


if __name__ == "__main__":
    main()
