"""Analyze impulse-continuation setup quality by UTC entry hour."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from aurus.backtest.scan_structural_setups import (
    StructuralSetupResult,
    TradeCandidate,
    load_research_data,
    scan_impulse_continuation,
    summarize_trades,
)


@dataclass(frozen=True)
class ImpulseHourResult:
    """Impulse-continuation metrics for one parameter set and UTC hour."""

    parameters: str
    entry_hour_utc: int
    trades: int
    profit_factor: float
    net_pnl: float
    max_drawdown: float
    average_monthly_pnl: float
    worst_monthly_pnl: float
    positive_months: int
    total_months: int


def analyze_impulse_hours(data_path: Path) -> list[ImpulseHourResult]:
    """Run impulse-continuation scans and split completed trades by entry hour."""

    data = load_research_data(data_path)
    rows: list[ImpulseHourResult] = []
    for reward_risk in (2.0, 2.5, 3.0):
        for impulse_bars in (3, 6, 12):
            for impulse_atr in (0.35, 0.50, 0.75):
                parameters = (
                    f"impulse_continuation:bars={impulse_bars}:atr={impulse_atr}:rr={reward_risk}"
                )
                trades = scan_impulse_continuation(
                    data=data,
                    impulse_bars=impulse_bars,
                    impulse_atr_multiplier=impulse_atr,
                    reward_risk=reward_risk,
                    setup=parameters,
                )
                rows.extend(hour_rows(parameters=parameters, trades=tuple(trades)))
    return sorted(rows, key=lambda row: (row.average_monthly_pnl, row.profit_factor), reverse=True)


def hour_rows(
    *,
    parameters: str,
    trades: tuple[TradeCandidate, ...],
) -> list[ImpulseHourResult]:
    """Summarize impulse trades by UTC entry hour."""

    trades_by_hour: defaultdict[int, list[TradeCandidate]] = defaultdict(list)
    for trade in trades:
        trades_by_hour[trade.entry_timestamp.hour].append(trade)

    rows: list[ImpulseHourResult] = []
    for hour, hour_trades in sorted(trades_by_hour.items()):
        summary = summarize_trades(setup=parameters, trades=tuple(hour_trades))
        rows.append(from_summary(parameters=parameters, hour=hour, summary=summary))
    return rows


def from_summary(
    *,
    parameters: str,
    hour: int,
    summary: StructuralSetupResult,
) -> ImpulseHourResult:
    """Create an hour result from a setup summary."""

    return ImpulseHourResult(
        parameters=parameters,
        entry_hour_utc=hour,
        trades=summary.trades,
        profit_factor=summary.profit_factor,
        net_pnl=summary.net_pnl,
        max_drawdown=summary.max_drawdown,
        average_monthly_pnl=summary.average_monthly_pnl,
        worst_monthly_pnl=summary.worst_monthly_pnl,
        positive_months=summary.positive_months,
        total_months=summary.total_months,
    )


def write_impulse_hour_csv(path: Path, rows: list[ImpulseHourResult]) -> None:
    """Write impulse-hour results to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "parameters",
                "entry_hour_utc",
                "trades",
                "profit_factor",
                "net_pnl",
                "max_drawdown",
                "average_monthly_pnl",
                "worst_monthly_pnl",
                "positive_months",
                "total_months",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.parameters,
                    row.entry_hour_utc,
                    row.trades,
                    row.profit_factor,
                    row.net_pnl,
                    row.max_drawdown,
                    row.average_monthly_pnl,
                    row.worst_monthly_pnl,
                    row.positive_months,
                    row.total_months,
                ]
            )


def format_impulse_hour_rows(rows: list[ImpulseHourResult], *, limit: int = 15) -> str:
    """Render top impulse-hour rows."""

    lines = ["hour trades PF net avg_month worst_month max_dd pos_months parameters"]
    for row in rows[:limit]:
        lines.append(
            " ".join(
                [
                    f"{row.entry_hour_utc:02d}",
                    str(row.trades),
                    f"{row.profit_factor:.6f}",
                    f"{row.net_pnl:.2f}",
                    f"{row.average_monthly_pnl:.2f}",
                    f"{row.worst_monthly_pnl:.2f}",
                    f"{row.max_drawdown:.2f}",
                    f"{row.positive_months}/{row.total_months}",
                    row.parameters,
                ]
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Analyze impulse setup quality by UTC hour.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/impulse-hour-analysis.csv"),
        type=Path,
        help="CSV output path.",
    )
    parser.add_argument("--top", default=15, type=int, help="Rows to print.")
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    rows = analyze_impulse_hours(args.data)
    write_impulse_hour_csv(args.output, rows)
    print(format_impulse_hour_rows(rows, limit=args.top))
    print(f"saved impulse-hour analysis: {args.output}")


if __name__ == "__main__":
    main()
