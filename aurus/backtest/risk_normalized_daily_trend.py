"""Risk-normalized reporting for the current daily trend strategy."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.run_daily_trend import current_daily_trend_config
from aurus.common.schemas import Side, SignalEvent
from aurus.data import load_real_xauusd_5m_csv
from aurus.strategy import DailyLondonTrendStrategy


@dataclass(frozen=True)
class RTrade:
    """Trade result in R-multiple terms."""

    exit_month: str
    realized_r: Decimal


@dataclass(frozen=True)
class RiskNormalizedResult:
    """Risk-normalized account metrics."""

    model: str
    risk_pct: Decimal
    max_risk_pct: Decimal
    ending_equity: Decimal
    net_return_pct: Decimal
    max_drawdown_pct: Decimal
    average_monthly_return_pct: Decimal
    best_monthly_return_pct: Decimal
    worst_monthly_return_pct: Decimal
    positive_months: int
    months_at_or_above_10pct: int
    total_months: int


def extract_daily_trend_r_trades(data_path: Path) -> tuple[RTrade, ...]:
    """Run the current daily trend branch and return realized R trades."""

    data = load_real_xauusd_5m_csv(data_path)
    strategy = DailyLondonTrendStrategy(
        context_bars=data.context_bars,
        config=current_daily_trend_config(quantity=Decimal("1")),
    )
    result = BacktestEngine(strategy=strategy).run(data.execution_bars)
    risk_by_timestamp: dict[object, Decimal] = {}
    for event in result.events:
        if isinstance(event, SignalEvent) and event.side != Side.FLAT:
            risk_by_timestamp[event.timestamp] = Decimal(str(event.features["risk_per_unit"]))

    trades: list[RTrade] = []
    for trade in result.trades:
        risk = risk_by_timestamp.get(trade.entry_timestamp)
        if risk is None or risk <= Decimal("0"):
            continue
        trades.append(
            RTrade(
                exit_month=f"{trade.exit_timestamp.year}-{trade.exit_timestamp.month:02d}",
                realized_r=trade.net_pnl / risk,
            )
        )
    return tuple(trades)


def simulate_risk_normalized_returns(
    trades: tuple[RTrade, ...],
    *,
    starting_equity: Decimal,
    risk_pct: Decimal,
) -> RiskNormalizedResult:
    """Apply percent-risk sizing to a sequence of realized R trades."""

    equity = starting_equity
    peak = starting_equity
    max_drawdown = Decimal("0")
    monthly_pnl: defaultdict[str, Decimal] = defaultdict(Decimal)

    for trade in trades:
        pnl = equity * risk_pct * trade.realized_r
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        monthly_pnl[trade.exit_month] += pnl

    return build_risk_result(
        model=f"fixed_{risk_pct}",
        risk_pct=risk_pct,
        max_risk_pct=risk_pct,
        starting_equity=starting_equity,
        ending_equity=equity,
        max_drawdown=max_drawdown,
        monthly_pnl=monthly_pnl,
    )


def simulate_progressive_risk_returns(
    trades: tuple[RTrade, ...],
    *,
    starting_equity: Decimal,
    initial_risk_pct: Decimal = Decimal("0.02"),
    step_risk_pct: Decimal = Decimal("0.005"),
    profit_step_pct: Decimal = Decimal("0.10"),
    max_risk_pct: Decimal = Decimal("0.05"),
    reset_on_drawdown: bool = True,
) -> RiskNormalizedResult:
    """Increase risk gradually as equity reaches new profit steps."""

    equity = starting_equity
    peak = starting_equity
    max_drawdown = Decimal("0")
    monthly_pnl: defaultdict[str, Decimal] = defaultdict(Decimal)

    for trade in trades:
        profit_steps = int(((peak / starting_equity) - Decimal("1")) / profit_step_pct)
        active_risk_pct = min(
            initial_risk_pct + (Decimal(profit_steps) * step_risk_pct),
            max_risk_pct,
        )
        if reset_on_drawdown and equity < peak:
            active_risk_pct = initial_risk_pct
        pnl = equity * active_risk_pct * trade.realized_r
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        monthly_pnl[trade.exit_month] += pnl

    return build_risk_result(
        model=(f"progressive_{initial_risk_pct}_{step_risk_pct}_{profit_step_pct}_{max_risk_pct}"),
        risk_pct=initial_risk_pct,
        max_risk_pct=max_risk_pct,
        starting_equity=starting_equity,
        ending_equity=equity,
        max_drawdown=max_drawdown,
        monthly_pnl=monthly_pnl,
    )


def build_risk_result(
    *,
    model: str,
    risk_pct: Decimal,
    max_risk_pct: Decimal,
    starting_equity: Decimal,
    ending_equity: Decimal,
    max_drawdown: Decimal,
    monthly_pnl: defaultdict[str, Decimal] | dict[str, Decimal],
) -> RiskNormalizedResult:
    """Build a risk-normalized result from equity and monthly PnL."""

    monthly_returns = tuple(
        (pnl / starting_equity) * Decimal("100") for pnl in monthly_pnl.values()
    )
    total_months = len(monthly_returns)
    average_monthly_return = (
        sum(monthly_returns, Decimal("0")) / Decimal(total_months) if total_months else Decimal("0")
    )
    return RiskNormalizedResult(
        model=model,
        risk_pct=risk_pct,
        max_risk_pct=max_risk_pct,
        ending_equity=ending_equity,
        net_return_pct=((ending_equity - starting_equity) / starting_equity) * Decimal("100"),
        max_drawdown_pct=(max_drawdown / starting_equity) * Decimal("100"),
        average_monthly_return_pct=average_monthly_return,
        best_monthly_return_pct=max(monthly_returns) if monthly_returns else Decimal("0"),
        worst_monthly_return_pct=min(monthly_returns) if monthly_returns else Decimal("0"),
        positive_months=sum(value > Decimal("0") for value in monthly_returns),
        months_at_or_above_10pct=sum(value >= Decimal("10") for value in monthly_returns),
        total_months=total_months,
    )


def write_risk_report(path: Path, rows: tuple[RiskNormalizedResult, ...]) -> None:
    """Write risk-normalized results to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "model",
                "risk_pct",
                "max_risk_pct",
                "ending_equity",
                "net_return_pct",
                "max_drawdown_pct",
                "average_monthly_return_pct",
                "best_monthly_return_pct",
                "worst_monthly_return_pct",
                "positive_months",
                "months_at_or_above_10pct",
                "total_months",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.model,
                    row.risk_pct,
                    row.max_risk_pct,
                    row.ending_equity,
                    row.net_return_pct,
                    row.max_drawdown_pct,
                    row.average_monthly_return_pct,
                    row.best_monthly_return_pct,
                    row.worst_monthly_return_pct,
                    row.positive_months,
                    row.months_at_or_above_10pct,
                    row.total_months,
                ]
            )


def format_risk_rows(rows: tuple[RiskNormalizedResult, ...]) -> str:
    """Render risk-normalized rows."""

    lines = [
        (
            "model risk_pct max_risk_pct ending_equity net_return% max_dd% "
            "avg_month% best_month% worst_month% >=10%months"
        )
    ]
    for row in rows:
        lines.append(
            " ".join(
                [
                    row.model,
                    str(row.risk_pct),
                    str(row.max_risk_pct),
                    str(row.ending_equity),
                    str(row.net_return_pct),
                    str(row.max_drawdown_pct),
                    str(row.average_monthly_return_pct),
                    str(row.best_monthly_return_pct),
                    str(row.worst_monthly_return_pct),
                    f"{row.months_at_or_above_10pct}/{row.total_months}",
                ]
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Report daily trend returns under percent risk.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/daily-trend-risk-normalized.csv"),
        type=Path,
        help="CSV output path.",
    )
    parser.add_argument(
        "--starting-equity",
        default=Decimal("10000"),
        type=Decimal,
        help="Starting equity.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    trades = extract_daily_trend_r_trades(args.data)
    rows = tuple(
        [
            *(
                simulate_risk_normalized_returns(
                    trades,
                    starting_equity=args.starting_equity,
                    risk_pct=risk_pct,
                )
                for risk_pct in (Decimal("0.005"), Decimal("0.01"), Decimal("0.02"))
            ),
            simulate_progressive_risk_returns(
                trades,
                starting_equity=args.starting_equity,
                initial_risk_pct=Decimal("0.02"),
                step_risk_pct=Decimal("0.005"),
                profit_step_pct=Decimal("0.10"),
                max_risk_pct=Decimal("0.05"),
            ),
            simulate_progressive_risk_returns(
                trades,
                starting_equity=args.starting_equity,
                initial_risk_pct=Decimal("0.02"),
                step_risk_pct=Decimal("0.01"),
                profit_step_pct=Decimal("0.10"),
                max_risk_pct=Decimal("0.08"),
            ),
            simulate_progressive_risk_returns(
                trades,
                starting_equity=args.starting_equity,
                initial_risk_pct=Decimal("0.02"),
                step_risk_pct=Decimal("0.01"),
                profit_step_pct=Decimal("0.20"),
                max_risk_pct=Decimal("0.10"),
            ),
        ]
    )
    write_risk_report(args.output, rows)
    print(format_risk_rows(rows))
    print(f"saved risk-normalized report: {args.output}")


if __name__ == "__main__":
    main()
