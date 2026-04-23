"""Scan deterministic daily channel-breakout structures for XAU/USD."""

from __future__ import annotations

import argparse
import math
from bisect import bisect_right
from pathlib import Path

from aurus.backtest.scan_structural_setups import (
    ResearchBar,
    ResearchData,
    StructuralSetupResult,
    TradeCandidate,
    bars_between,
    format_float,
    load_research_data,
    simulate_exit,
    summarize_trades,
    write_results,
)


def scan_channel_breakouts(data: ResearchData) -> list[StructuralSetupResult]:
    """Scan a bounded grid of previous-channel breakout structures."""

    trades_by_setup: dict[str, list[TradeCandidate]] = {}
    for channel_hours in (24, 48, 72):
        for start_hour in (5, 6, 7, 12):
            for exit_hour in (21, 22):
                if exit_hour <= start_hour + 4:
                    continue
                for reward_risk in (2.0, 3.0, 4.0):
                    for stop_mode in ("channel", "half_channel"):
                        setup = (
                            "daily_channel_breakout:"
                            f"hours={channel_hours}:start={start_hour}:exit={exit_hour}:"
                            f"stop={stop_mode}:rr={reward_risk}"
                        )
                        trades_by_setup[setup] = scan_single_channel_breakout(
                            data=data,
                            channel_hours=channel_hours,
                            start_hour=start_hour,
                            exit_hour=exit_hour,
                            stop_mode=stop_mode,
                            atr_stop_multiplier=0.0,
                            reward_risk=reward_risk,
                            setup=setup,
                        )
                    for atr_stop_multiplier in (2.0, 3.0):
                        setup = (
                            "daily_channel_breakout:"
                            f"hours={channel_hours}:start={start_hour}:exit={exit_hour}:"
                            f"stop=atr{atr_stop_multiplier}:rr={reward_risk}"
                        )
                        trades_by_setup[setup] = scan_single_channel_breakout(
                            data=data,
                            channel_hours=channel_hours,
                            start_hour=start_hour,
                            exit_hour=exit_hour,
                            stop_mode="atr",
                            atr_stop_multiplier=atr_stop_multiplier,
                            reward_risk=reward_risk,
                            setup=setup,
                        )

    results = [
        summarize_trades(setup=setup, trades=tuple(trades))
        for setup, trades in trades_by_setup.items()
        if trades
    ]
    return sorted(
        results, key=lambda row: (row.average_monthly_pnl, row.profit_factor), reverse=True
    )


def scan_single_channel_breakout(
    *,
    data: ResearchData,
    channel_hours: int,
    start_hour: int,
    exit_hour: int,
    stop_mode: str,
    atr_stop_multiplier: float,
    reward_risk: float,
    setup: str,
) -> list[TradeCandidate]:
    """Enter the first break of a prior closed-hour channel each day."""

    trades: list[TradeCandidate] = []
    for day, day_bars in data.bars_by_day.items():
        trade_bars = bars_between(day_bars, day, start_hour, exit_hour)
        if len(trade_bars) < 12:
            continue
        context_index = bisect_right(data.hour_timestamps, trade_bars[0].timestamp) - 1
        if context_index < channel_hours:
            continue
        channel = data.hour_bars[context_index - channel_hours + 1 : context_index + 1]
        context_atr = data.hour_atr[context_index]
        if not channel or not math.isfinite(context_atr) or context_atr <= 0.0:
            continue
        channel_high = max(hour.high for hour in channel)
        channel_low = min(hour.low for hour in channel)
        risk = channel_risk(
            channel_high=channel_high,
            channel_low=channel_low,
            context_atr=context_atr,
            stop_mode=stop_mode,
            atr_stop_multiplier=atr_stop_multiplier,
        )
        if risk <= 0.0:
            continue
        trade = first_channel_breakout_trade(
            setup=setup,
            trade_bars=trade_bars,
            channel_high=channel_high,
            channel_low=channel_low,
            risk=risk,
            reward_risk=reward_risk,
        )
        if trade is not None:
            trades.append(trade)
    return trades


def channel_risk(
    *,
    channel_high: float,
    channel_low: float,
    context_atr: float,
    stop_mode: str,
    atr_stop_multiplier: float,
) -> float:
    """Return stop distance for a channel breakout variant."""

    channel_width = channel_high - channel_low
    if stop_mode == "channel":
        return channel_width
    if stop_mode == "half_channel":
        return channel_width / 2.0
    if stop_mode == "atr":
        return context_atr * atr_stop_multiplier
    msg = f"unsupported stop mode: {stop_mode}"
    raise ValueError(msg)


def first_channel_breakout_trade(
    *,
    setup: str,
    trade_bars: tuple[ResearchBar, ...],
    channel_high: float,
    channel_low: float,
    risk: float,
    reward_risk: float,
) -> TradeCandidate | None:
    """Return the first completed channel-breakout trade in a day."""

    for bar_index, bar in enumerate(trade_bars):
        if bar.high > channel_high:
            return simulate_exit(
                setup=setup,
                side=1,
                entry_bar=bar,
                future_bars=trade_bars[bar_index + 1 :],
                risk=risk,
                reward_risk=reward_risk,
            )
        if bar.low < channel_low:
            return simulate_exit(
                setup=setup,
                side=-1,
                entry_bar=bar,
                future_bars=trade_bars[bar_index + 1 :],
                risk=risk,
                reward_risk=reward_risk,
            )
    return None


def write_channel_results(path: Path, rows: list[StructuralSetupResult]) -> None:
    """Write channel-breakout scan results to CSV."""

    write_results(path, rows)


def format_channel_results(rows: list[StructuralSetupResult], *, limit: int = 10) -> str:
    """Format channel-breakout scan results."""

    lines = ["setup trades PF net avg_month worst_month max_dd pos_months parameters"]
    for row in rows[:limit]:
        lines.append(
            " ".join(
                [
                    row.setup,
                    str(row.trades),
                    format_float(row.profit_factor),
                    format_float(row.net_pnl),
                    format_float(row.average_monthly_pnl),
                    format_float(row.worst_monthly_pnl),
                    format_float(row.max_drawdown),
                    f"{row.positive_months}/{row.total_months}",
                    row.parameters,
                ]
            )
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Scan deterministic XAU/USD channel breakouts.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/channel-breakout-scan.csv"),
        type=Path,
        help="CSV path for scan results.",
    )
    parser.add_argument("--top", default=15, type=int, help="Number of rows to print.")
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_research_data(args.data)
    rows = scan_channel_breakouts(data)
    write_channel_results(args.output, rows)
    print(format_channel_results(rows, limit=args.top))
    print(f"saved channel breakout scan: {args.output}")


if __name__ == "__main__":
    main()
