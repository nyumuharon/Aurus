"""Run the daily London trend strategy on real XAU/USD data."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig, BacktestResult
from aurus.data import IngestedMarketData, load_real_xauusd_5m_csv
from aurus.ops.metrics import calculate_metrics
from aurus.ops.summary import format_decimal
from aurus.strategy import DailyLondonTrendConfig, DailyLondonTrendStrategy, DailyTrendWindow


def current_daily_trend_config(*, quantity: Decimal = Decimal("1")) -> DailyLondonTrendConfig:
    """Return the current daily-trading research configuration."""

    return DailyLondonTrendConfig(
        context_ema_period=20,
        context_atr_period=14,
        windows=(DailyTrendWindow(label="pre_london_full", entry_hour_utc=6, exit_hour_utc=22),),
        atr_stop_multiplier=Decimal("3"),
        reward_risk=Decimal("3"),
        quantity=quantity,
    )


def current_daily_trend_backtest_config() -> BacktestConfig:
    """Return static-stop execution assumptions for the daily trend strategy."""

    return BacktestConfig(record_events=False)


def run_daily_trend_backtest(
    *,
    data: IngestedMarketData,
    strategy_config: DailyLondonTrendConfig | None = None,
    backtest_config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run the daily trend strategy against already-ingested real bars."""

    strategy = DailyLondonTrendStrategy(
        context_bars=data.context_bars,
        config=strategy_config or current_daily_trend_config(),
    )
    return BacktestEngine(
        strategy=strategy,
        config=backtest_config or current_daily_trend_backtest_config(),
    ).run(data.execution_bars)


def format_daily_trend_summary(
    result: BacktestResult,
    *,
    starting_equity: Decimal = Decimal("10000"),
) -> str:
    """Render metrics plus the yearly/monthly account-style breakdown."""

    metrics = calculate_metrics(result.trades, result.equity_curve)
    annual_pnl = realized_pnl_by_year(result)
    latest_year = max(annual_pnl) if annual_pnl else None
    lines = [
        "Aurus daily London trend backtest summary",
        f"total trades: {metrics.trade_count}",
        f"win rate: {metrics.win_rate}",
        f"profit factor: {format_decimal(metrics.profit_factor)}",
        f"max drawdown: {metrics.max_drawdown}",
        f"net PnL: {metrics.total_pnl}",
        f"net return: {format_return_pct(metrics.total_pnl, starting_equity)}",
        f"max drawdown return: {format_return_pct(metrics.max_drawdown, starting_equity)}",
        f"starting equity: {starting_equity}",
        "yearly PnL:",
    ]
    lines.extend(format_yearly_pnl(annual_pnl, starting_equity=starting_equity))
    if latest_year is not None:
        lines.append(f"{latest_year} monthly PnL:")
        lines.extend(
            format_monthly_pnl(
                realized_pnl_by_month(result, year=latest_year),
                starting_equity=starting_equity,
            )
        )
    return "\n".join(lines)


def realized_pnl_by_year(result: BacktestResult) -> dict[int, Decimal]:
    """Group closed-trade realized PnL by exit year."""

    pnl_by_year: defaultdict[int, Decimal] = defaultdict(Decimal)
    for trade in result.trades:
        pnl_by_year[trade.exit_timestamp.year] += trade.net_pnl
    return dict(sorted(pnl_by_year.items()))


def realized_pnl_by_month(result: BacktestResult, *, year: int) -> dict[datetime, Decimal]:
    """Group closed-trade realized PnL by month for a year."""

    pnl_by_month: defaultdict[datetime, Decimal] = defaultdict(Decimal)
    for trade in result.trades:
        if trade.exit_timestamp.year != year:
            continue
        month = datetime(
            trade.exit_timestamp.year,
            trade.exit_timestamp.month,
            1,
            tzinfo=trade.exit_timestamp.tzinfo,
        )
        pnl_by_month[month] += trade.net_pnl
    return dict(sorted(pnl_by_month.items()))


def format_yearly_pnl(
    pnl_by_year: Mapping[int, Decimal],
    *,
    starting_equity: Decimal,
) -> list[str]:
    """Render yearly PnL with running ending equity."""

    if not pnl_by_year:
        return ["none"]
    ending_equity = starting_equity
    rows: list[str] = []
    for year, pnl in pnl_by_year.items():
        ending_equity += pnl
        rows.append(
            f"{year}: PnL {pnl}, return {format_return_pct(pnl, starting_equity)}, "
            f"ending equity {ending_equity}"
        )
    return rows


def format_monthly_pnl(
    pnl_by_month: Mapping[datetime, Decimal],
    *,
    starting_equity: Decimal = Decimal("10000"),
) -> list[str]:
    """Render monthly PnL rows."""

    if not pnl_by_month:
        return ["none"]
    return [
        (
            f"{month.year}-{month.month:02d}: PnL {pnl}, "
            f"return {format_return_pct(pnl, starting_equity)}"
        )
        for month, pnl in pnl_by_month.items()
    ]


def format_return_pct(value: Decimal, base: Decimal) -> str:
    """Render a return percentage using the supplied account base."""

    if base == Decimal("0"):
        return "n/a"
    return f"{format_decimal((value / base) * Decimal('100'))}%"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run daily London trend on real XAU/USD CSV.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--starting-equity",
        default=Decimal("10000"),
        type=Decimal,
        help="Starting equity for yearly/monthly reporting.",
    )
    parser.add_argument(
        "--quantity",
        default=Decimal("1"),
        type=Decimal,
        help="Fixed strategy quantity for sizing what-if reporting.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_real_xauusd_5m_csv(args.data)
    result = run_daily_trend_backtest(
        data=data,
        strategy_config=current_daily_trend_config(quantity=args.quantity),
    )
    print(format_daily_trend_summary(result, starting_equity=args.starting_equity))


if __name__ == "__main__":
    main()
