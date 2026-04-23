"""Analyze deterministic portfolios of structural XAU/USD setup components."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from aurus.backtest.run_daily_trend import current_daily_trend_config, run_daily_trend_backtest
from aurus.backtest.scan_channel_breakouts import scan_single_channel_breakout
from aurus.backtest.scan_structural_setups import (
    TradeCandidate,
    load_research_data,
    max_drawdown,
    profit_factor,
)
from aurus.backtest.types import TradeRecord
from aurus.data import load_real_xauusd_5m_csv


@dataclass(frozen=True)
class PortfolioTrade:
    """One closed trade from a named structural component."""

    source: str
    exit_timestamp: str
    pnl: float


@dataclass(frozen=True)
class PortfolioSummary:
    """Aggregate metrics for a structural portfolio."""

    label: str
    trades: int
    profit_factor: float
    net_pnl: float
    average_monthly_pnl: float
    worst_monthly_pnl: float
    max_drawdown: float
    positive_months: int
    total_months: int


def current_channel_component(data_path: Path) -> list[TradeCandidate]:
    """Return the current best channel-breakout research component."""

    data = load_research_data(data_path)
    return scan_single_channel_breakout(
        data=data,
        channel_hours=72,
        start_hour=7,
        exit_hour=22,
        stop_mode="atr",
        atr_stop_multiplier=2.0,
        reward_risk=2.0,
        setup="daily_channel_breakout:hours=72:start=7:exit=22:stop=atr2.0:rr=2.0",
    )


def daily_trend_component(data_path: Path) -> tuple[TradeRecord, ...]:
    """Run the current daily trend baseline component."""

    data = load_real_xauusd_5m_csv(data_path)
    result = run_daily_trend_backtest(
        data=data,
        strategy_config=current_daily_trend_config(quantity=Decimal("1")),
    )
    return result.trades


def combine_components(
    *,
    daily_trades: tuple[TradeRecord, ...],
    channel_trades: list[TradeCandidate],
) -> list[PortfolioTrade]:
    """Merge daily trend and channel-breakout trades in exit-time order."""

    trades: list[PortfolioTrade] = []
    for trade in daily_trades:
        trades.append(
            PortfolioTrade(
                source="daily_trend",
                exit_timestamp=trade.exit_timestamp.isoformat(),
                pnl=float(trade.net_pnl),
            )
        )
    for channel_trade in channel_trades:
        trades.append(
            PortfolioTrade(
                source="channel_breakout",
                exit_timestamp=channel_trade.exit_timestamp.isoformat(),
                pnl=channel_trade.pnl,
            )
        )
    return sorted(trades, key=lambda trade: trade.exit_timestamp)


def summarize_portfolio(label: str, trades: list[PortfolioTrade]) -> PortfolioSummary:
    """Summarize a structural portfolio."""

    pnl_values = tuple(trade.pnl for trade in trades)
    monthly = monthly_pnl(trades)
    monthly_values = tuple(monthly.values())
    return PortfolioSummary(
        label=label,
        trades=len(trades),
        profit_factor=profit_factor(pnl_values),
        net_pnl=sum(pnl_values),
        average_monthly_pnl=sum(monthly_values) / float(len(monthly_values)),
        worst_monthly_pnl=min(monthly_values),
        max_drawdown=max_drawdown(pnl_values),
        positive_months=sum(value > 0.0 for value in monthly_values),
        total_months=len(monthly_values),
    )


def monthly_pnl(trades: list[PortfolioTrade]) -> dict[str, float]:
    """Group portfolio PnL by exit month."""

    output: defaultdict[str, float] = defaultdict(float)
    for trade in trades:
        output[trade.exit_timestamp[:7]] += trade.pnl
    return dict(sorted(output.items()))


def write_portfolio_trades(path: Path, trades: list[PortfolioTrade]) -> None:
    """Write component-level portfolio trades."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "exit_timestamp", "pnl"])
        for trade in trades:
            writer.writerow([trade.source, trade.exit_timestamp, trade.pnl])


def format_portfolio_summaries(rows: list[PortfolioSummary]) -> str:
    """Format portfolio summaries."""

    lines = ["label trades PF net avg_month worst_month max_dd pos_months"]
    for row in rows:
        lines.append(
            " ".join(
                [
                    row.label,
                    str(row.trades),
                    f"{row.profit_factor:.6f}".rstrip("0").rstrip("."),
                    f"{row.net_pnl:.6f}".rstrip("0").rstrip("."),
                    f"{row.average_monthly_pnl:.6f}".rstrip("0").rstrip("."),
                    f"{row.worst_monthly_pnl:.6f}".rstrip("0").rstrip("."),
                    f"{row.max_drawdown:.6f}".rstrip("0").rstrip("."),
                    f"{row.positive_months}/{row.total_months}",
                ]
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Analyze Aurus structural setup portfolios.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/structure-portfolio-trades.csv"),
        type=Path,
        help="CSV path for merged portfolio trades.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    daily_trades = daily_trend_component(args.data)
    channel_trades = current_channel_component(args.data)
    portfolio_trades = combine_components(
        daily_trades=daily_trades,
        channel_trades=channel_trades,
    )
    summaries = [
        summarize_portfolio(
            "daily_trend",
            [
                PortfolioTrade(
                    source="daily_trend",
                    exit_timestamp=trade.exit_timestamp.isoformat(),
                    pnl=float(trade.net_pnl),
                )
                for trade in daily_trades
            ],
        ),
        summarize_portfolio(
            "channel_breakout",
            [
                PortfolioTrade(
                    source="channel_breakout",
                    exit_timestamp=trade.exit_timestamp.isoformat(),
                    pnl=trade.pnl,
                )
                for trade in channel_trades
            ],
        ),
        summarize_portfolio("combined", portfolio_trades),
    ]
    write_portfolio_trades(args.output, portfolio_trades)
    print(format_portfolio_summaries(summaries))
    print(f"saved structural portfolio trades: {args.output}")


if __name__ == "__main__":
    main()
