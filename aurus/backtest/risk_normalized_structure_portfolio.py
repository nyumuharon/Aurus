"""Risk-normalized reporting for the current structural portfolio."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from aurus.backtest.analyze_structure_portfolio import (
    current_channel_component,
    current_london_reversal_component,
    current_ny_impulse_component,
)
from aurus.backtest.engine import BacktestEngine
from aurus.backtest.risk_normalized_daily_trend import (
    RiskNormalizedResult,
    RTrade,
    build_risk_result,
    format_risk_rows,
    simulate_progressive_risk_returns,
)
from aurus.backtest.run_daily_trend import current_daily_trend_config
from aurus.common.schemas import Side, SignalEvent
from aurus.data import load_real_xauusd_5m_csv
from aurus.strategy import DailyLondonTrendStrategy


@dataclass(frozen=True)
class PortfolioRTrade:
    """Risk-normalized trade with exact exit ordering."""

    source: str
    exit_timestamp: datetime
    realized_r: Decimal


def extract_daily_trend_portfolio_r_trades(data_path: Path) -> tuple[PortfolioRTrade, ...]:
    """Run the current daily trend branch and return realized R trades."""

    data = load_real_xauusd_5m_csv(data_path)
    strategy = DailyLondonTrendStrategy(
        context_bars=data.context_bars,
        config=current_daily_trend_config(quantity=Decimal("1")),
    )
    result = BacktestEngine(strategy=strategy).run(data.execution_bars)
    risk_by_timestamp: dict[datetime, Decimal] = {}
    for event in result.events:
        if isinstance(event, SignalEvent) and event.side != Side.FLAT:
            risk_by_timestamp[event.timestamp] = Decimal(str(event.features["risk_per_unit"]))

    trades: list[PortfolioRTrade] = []
    for trade in result.trades:
        risk = risk_by_timestamp.get(trade.entry_timestamp)
        if risk is None or risk <= Decimal("0"):
            continue
        trades.append(
            PortfolioRTrade(
                source="daily_trend",
                exit_timestamp=trade.exit_timestamp,
                realized_r=trade.net_pnl / risk,
            )
        )
    return tuple(trades)


def extract_channel_breakout_portfolio_r_trades(data_path: Path) -> tuple[PortfolioRTrade, ...]:
    """Return realized R trades for the current channel-breakout component."""

    trades = current_channel_component(data_path)
    return tuple(
        PortfolioRTrade(
            source="channel_breakout",
            exit_timestamp=trade.exit_timestamp,
            realized_r=Decimal(str(trade.realized_r)),
        )
        for trade in trades
        if trade.risk_per_unit > 0.0
    )


def extract_ny_impulse_portfolio_r_trades(data_path: Path) -> tuple[PortfolioRTrade, ...]:
    """Return realized R trades for the selective NY impulse component."""

    trades = current_ny_impulse_component(data_path)
    return tuple(
        PortfolioRTrade(
            source="ny_impulse",
            exit_timestamp=trade.exit_timestamp,
            realized_r=Decimal(str(trade.realized_r)),
        )
        for trade in trades
        if trade.risk_per_unit > 0.0
    )


def extract_london_reversal_portfolio_r_trades(data_path: Path) -> tuple[PortfolioRTrade, ...]:
    """Return realized R trades for the selective London reversal component."""

    trades = current_london_reversal_component(data_path)
    return tuple(
        PortfolioRTrade(
            source="london_reversal",
            exit_timestamp=trade.exit_timestamp,
            realized_r=Decimal(str(trade.realized_r)),
        )
        for trade in trades
        if trade.risk_per_unit > 0.0
    )


def combine_portfolio_r_trades(
    *,
    daily_trades: tuple[PortfolioRTrade, ...],
    channel_trades: tuple[PortfolioRTrade, ...],
    impulse_trades: tuple[PortfolioRTrade, ...] = (),
    reversal_trades: tuple[PortfolioRTrade, ...] = (),
) -> tuple[PortfolioRTrade, ...]:
    """Return combined portfolio R trades in exit-time order."""

    return tuple(
        sorted(
            (
                *daily_trades,
                *channel_trades,
                *impulse_trades,
                *reversal_trades,
            ),
            key=lambda trade: trade.exit_timestamp,
        )
    )


def simulate_portfolio_risk_normalized_returns(
    trades: tuple[PortfolioRTrade, ...],
    *,
    starting_equity: Decimal,
    risk_pct: Decimal,
) -> tuple[RiskNormalizedResult, dict[str, Decimal]]:
    """Apply fixed percent-risk sizing to portfolio R trades."""

    equity = starting_equity
    peak = starting_equity
    max_drawdown = Decimal("0")
    monthly_pnl: defaultdict[str, Decimal] = defaultdict(Decimal)

    for trade in trades:
        pnl = equity * risk_pct * trade.realized_r
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        monthly_pnl[f"{trade.exit_timestamp.year}-{trade.exit_timestamp.month:02d}"] += pnl

    return (
        build_risk_result(
            model=f"combined_fixed_{risk_pct}",
            risk_pct=risk_pct,
            max_risk_pct=risk_pct,
            starting_equity=starting_equity,
            ending_equity=equity,
            max_drawdown=max_drawdown,
            monthly_pnl=monthly_pnl,
        ),
        dict(sorted(monthly_pnl.items())),
    )


def simulate_progressive_portfolio_returns(
    trades: tuple[PortfolioRTrade, ...],
    *,
    starting_equity: Decimal,
    initial_risk_pct: Decimal = Decimal("0.02"),
    step_risk_pct: Decimal = Decimal("0.005"),
    profit_step_pct: Decimal = Decimal("0.10"),
    max_risk_pct: Decimal = Decimal("0.05"),
) -> RiskNormalizedResult:
    """Apply progressive percent-risk sizing to portfolio R trades."""

    simple_trades = tuple(
        RTrade(
            exit_month=f"{trade.exit_timestamp.year}-{trade.exit_timestamp.month:02d}",
            realized_r=trade.realized_r,
        )
        for trade in trades
    )
    return simulate_progressive_risk_returns(
        simple_trades,
        starting_equity=starting_equity,
        initial_risk_pct=initial_risk_pct,
        step_risk_pct=step_risk_pct,
        profit_step_pct=profit_step_pct,
        max_risk_pct=max_risk_pct,
    )


def write_monthly_returns(path: Path, monthly_pnl: dict[str, Decimal]) -> None:
    """Write monthly PnL rows for the combined portfolio."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["month", "pnl"])
        for month, pnl in monthly_pnl.items():
            writer.writerow([month, pnl])


def format_monthly_returns(
    monthly_pnl: dict[str, Decimal],
    *,
    starting_equity: Decimal,
    year: int | None = None,
) -> str:
    """Render monthly PnL and account return percentages."""

    lines = ["month pnl return_pct"]
    for month, pnl in monthly_pnl.items():
        if year is not None and not month.startswith(f"{year}-"):
            continue
        return_pct = (pnl / starting_equity) * Decimal("100")
        lines.append(f"{month} {pnl} {return_pct}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Report structural portfolio returns under percent risk."
    )
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/structure-portfolio-risk-normalized.csv"),
        type=Path,
        help="CSV output path for risk-normalized summaries.",
    )
    parser.add_argument(
        "--monthly-output",
        default=Path("artifacts/structure-portfolio-monthly-pnl.csv"),
        type=Path,
        help="CSV output path for monthly PnL rows.",
    )
    parser.add_argument(
        "--starting-equity",
        default=Decimal("10000"),
        type=Decimal,
        help="Starting equity for account return simulation.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    daily_trades = extract_daily_trend_portfolio_r_trades(args.data)
    channel_trades = extract_channel_breakout_portfolio_r_trades(args.data)
    impulse_trades = extract_ny_impulse_portfolio_r_trades(args.data)
    reversal_trades = extract_london_reversal_portfolio_r_trades(args.data)
    combined_trades = combine_portfolio_r_trades(
        daily_trades=daily_trades,
        channel_trades=channel_trades,
        impulse_trades=impulse_trades,
        reversal_trades=reversal_trades,
    )
    fixed_rows: list[RiskNormalizedResult] = []
    fixed_monthly: dict[str, Decimal] = {}
    for risk_pct in (Decimal("0.005"), Decimal("0.01"), Decimal("0.02")):
        row, monthly_pnl = simulate_portfolio_risk_normalized_returns(
            combined_trades,
            starting_equity=args.starting_equity,
            risk_pct=risk_pct,
        )
        fixed_rows.append(row)
        if risk_pct == Decimal("0.02"):
            fixed_monthly = monthly_pnl
    progressive_rows = [
        simulate_progressive_portfolio_returns(
            combined_trades,
            starting_equity=args.starting_equity,
            max_risk_pct=Decimal("0.05"),
        )
    ]
    rows = tuple((*fixed_rows, *progressive_rows))
    write_risk_report(args.output, rows)
    write_monthly_returns(args.monthly_output, fixed_monthly)
    print(format_risk_rows(rows))
    print()
    print("2026 fixed 2% monthly")
    print(format_monthly_returns(fixed_monthly, starting_equity=args.starting_equity, year=2026))
    print(f"saved portfolio risk report: {args.output}")
    print(f"saved portfolio monthly report: {args.monthly_output}")


def write_risk_report(path: Path, rows: tuple[RiskNormalizedResult, ...]) -> None:
    """Write risk-normalized summary rows."""

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


if __name__ == "__main__":
    main()
