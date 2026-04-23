"""Scan deterministic XAU/USD structural setup families."""

from __future__ import annotations

import argparse
import csv
import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class ResearchBar:
    """Lightweight float bar for high-volume structural research scans."""

    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    spread: float


@dataclass(frozen=True)
class HourBar:
    """Closed 1H context bar."""

    timestamp: datetime
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TradeCandidate:
    """Completed deterministic research trade."""

    setup: str
    entry_timestamp: datetime
    exit_timestamp: datetime
    side: int
    entry_price: float
    exit_price: float
    risk_per_unit: float
    pnl: float
    realized_r: float
    exit_reason: str


@dataclass(frozen=True)
class StructuralSetupResult:
    """Metrics for a structural setup scan."""

    setup: str
    parameters: str
    trades: int
    win_rate: float
    profit_factor: float
    net_pnl: float
    max_drawdown: float
    average_r: float
    average_monthly_pnl: float
    worst_monthly_pnl: float
    best_monthly_pnl: float
    positive_months: int
    total_months: int


@dataclass(frozen=True)
class ResearchData:
    """Precomputed structures for fast setup scans."""

    bars: tuple[ResearchBar, ...]
    bars_by_day: dict[datetime, tuple[ResearchBar, ...]]
    hour_bars: tuple[HourBar, ...]
    hour_timestamps: tuple[datetime, ...]
    hour_ema: tuple[float, ...]
    hour_atr: tuple[float, ...]


def load_research_data(path: Path) -> ResearchData:
    """Load M5 CSV data and precompute hourly trend context."""

    bars: list[ResearchBar] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            timestamp = parse_timestamp(row["timestamp"])
            bars.append(
                ResearchBar(
                    index=index,
                    timestamp=timestamp,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    spread=float(row.get("spread") or 0),
                )
            )

    day_map: defaultdict[datetime, list[ResearchBar]] = defaultdict(list)
    for bar in bars:
        day_start = datetime(
            bar.timestamp.year,
            bar.timestamp.month,
            bar.timestamp.day,
            tzinfo=UTC,
        )
        day_map[day_start].append(bar)

    hour_bars = aggregate_hour_bars(tuple(bars))
    hour_closes = [bar.close for bar in hour_bars]
    return ResearchData(
        bars=tuple(bars),
        bars_by_day={day: tuple(day_bars) for day, day_bars in sorted(day_map.items())},
        hour_bars=hour_bars,
        hour_timestamps=tuple(bar.timestamp for bar in hour_bars),
        hour_ema=tuple(ema(hour_closes, 20)),
        hour_atr=tuple(atr(hour_bars, 14)),
    )


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp as UTC."""

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    return datetime.fromisoformat(normalized).astimezone(UTC)


def aggregate_hour_bars(bars: tuple[ResearchBar, ...]) -> tuple[HourBar, ...]:
    """Aggregate complete M5 windows into closed hourly bars."""

    grouped: defaultdict[datetime, list[ResearchBar]] = defaultdict(list)
    for bar in bars:
        hour_start = bar.timestamp.replace(minute=0, second=0, microsecond=0)
        grouped[hour_start].append(bar)

    hourly: list[HourBar] = []
    for hour_start in sorted(grouped):
        window = sorted(grouped[hour_start], key=lambda bar: bar.timestamp)
        if len(window) != 12:
            continue
        hourly.append(
            HourBar(
                timestamp=hour_start + timedelta(hours=1),
                high=max(bar.high for bar in window),
                low=min(bar.low for bar in window),
                close=window[-1].close,
            )
        )
    return tuple(hourly)


def ema(values: list[float], period: int) -> list[float]:
    """Calculate EMA values."""

    alpha = 2.0 / float(period + 1)
    output: list[float] = []
    previous: float | None = None
    for value in values:
        previous = value if previous is None else (value * alpha) + (previous * (1.0 - alpha))
        output.append(previous)
    return output


def atr(bars: tuple[HourBar, ...], period: int) -> list[float]:
    """Calculate Wilder ATR values."""

    output: list[float] = []
    true_ranges: list[float] = []
    previous_close: float | None = None
    previous_atr: float | None = None
    for bar in bars:
        true_range = (
            bar.high - bar.low
            if previous_close is None
            else max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
        previous_close = bar.close
        true_ranges.append(true_range)
        if len(true_ranges) < period:
            output.append(math.nan)
        elif len(true_ranges) == period:
            previous_atr = sum(true_ranges[-period:]) / float(period)
            output.append(previous_atr)
        else:
            assert previous_atr is not None
            previous_atr = ((previous_atr * float(period - 1)) + true_range) / float(period)
            output.append(previous_atr)
    return output


def scan_structural_setups(data: ResearchData) -> list[StructuralSetupResult]:
    """Scan all currently defined structural setup families."""

    trades_by_setup: dict[str, list[TradeCandidate]] = {}
    for reward_risk in (2.0, 2.5, 3.0):
        for range_name, start_hour, end_hour, exit_hour in (
            ("asia", 0, 6, 22),
            ("pre_london", 5, 7, 22),
            ("london_ib", 7, 8, 22),
            ("ny_open", 12, 13, 22),
        ):
            opening_key = f"opening_range_breakout:{range_name}:rr={reward_risk}"
            trades_by_setup[opening_key] = scan_opening_range_breakout(
                data=data,
                range_start_hour=start_hour,
                range_end_hour=end_hour,
                exit_hour=exit_hour,
                reward_risk=reward_risk,
                setup=opening_key,
            )
            reversal_key = f"failed_breakout_reversal:{range_name}:rr={reward_risk}"
            trades_by_setup[reversal_key] = scan_failed_breakout_reversal(
                data=data,
                range_start_hour=start_hour,
                range_end_hour=end_hour,
                exit_hour=exit_hour,
                reward_risk=reward_risk,
                setup=reversal_key,
            )

        for impulse_bars in (3, 6, 12):
            for impulse_atr in (0.35, 0.50, 0.75):
                impulse_key = (
                    f"impulse_continuation:bars={impulse_bars}:atr={impulse_atr}:rr={reward_risk}"
                )
                trades_by_setup[impulse_key] = scan_impulse_continuation(
                    data=data,
                    impulse_bars=impulse_bars,
                    impulse_atr_multiplier=impulse_atr,
                    reward_risk=reward_risk,
                    setup=impulse_key,
                )

    results = [
        summarize_trades(setup=setup, trades=tuple(trades))
        for setup, trades in trades_by_setup.items()
        if trades
    ]
    return sorted(
        results, key=lambda row: (row.average_monthly_pnl, row.profit_factor), reverse=True
    )


def scan_opening_range_breakout(
    *,
    data: ResearchData,
    range_start_hour: int,
    range_end_hour: int,
    exit_hour: int,
    reward_risk: float,
    setup: str,
) -> list[TradeCandidate]:
    """Enter first break of a defined opening range."""

    trades: list[TradeCandidate] = []
    for day, day_bars in data.bars_by_day.items():
        range_bars = bars_between(day_bars, day, range_start_hour, range_end_hour)
        trade_bars = bars_between(day_bars, day, range_end_hour, exit_hour)
        if len(range_bars) < 6 or len(trade_bars) < 6:
            continue
        range_high = max(bar.high for bar in range_bars)
        range_low = min(bar.low for bar in range_bars)
        for bar_index, bar in enumerate(trade_bars):
            if bar.high > range_high:
                risk = max(bar.close - range_low, 0.0)
                trade = simulate_exit(
                    setup=setup,
                    side=1,
                    entry_bar=bar,
                    future_bars=trade_bars[bar_index + 1 :],
                    risk=risk,
                    reward_risk=reward_risk,
                )
                if trade is not None:
                    trades.append(trade)
                break
            if bar.low < range_low:
                risk = max(range_high - bar.close, 0.0)
                trade = simulate_exit(
                    setup=setup,
                    side=-1,
                    entry_bar=bar,
                    future_bars=trade_bars[bar_index + 1 :],
                    risk=risk,
                    reward_risk=reward_risk,
                )
                if trade is not None:
                    trades.append(trade)
                break
    return trades


def scan_failed_breakout_reversal(
    *,
    data: ResearchData,
    range_start_hour: int,
    range_end_hour: int,
    exit_hour: int,
    reward_risk: float,
    setup: str,
) -> list[TradeCandidate]:
    """Fade a sweep outside a prior range that closes back inside the range."""

    trades: list[TradeCandidate] = []
    for day, day_bars in data.bars_by_day.items():
        range_bars = bars_between(day_bars, day, range_start_hour, range_end_hour)
        trade_bars = bars_between(day_bars, day, range_end_hour, exit_hour)
        if len(range_bars) < 6 or len(trade_bars) < 6:
            continue
        range_high = max(bar.high for bar in range_bars)
        range_low = min(bar.low for bar in range_bars)
        for bar_index, bar in enumerate(trade_bars):
            if bar.high > range_high and bar.close < range_high:
                risk = max(bar.high - bar.close, 0.0)
                trade = simulate_exit(
                    setup=setup,
                    side=-1,
                    entry_bar=bar,
                    future_bars=trade_bars[bar_index + 1 :],
                    risk=risk,
                    reward_risk=reward_risk,
                )
                if trade is not None:
                    trades.append(trade)
                break
            if bar.low < range_low and bar.close > range_low:
                risk = max(bar.close - bar.low, 0.0)
                trade = simulate_exit(
                    setup=setup,
                    side=1,
                    entry_bar=bar,
                    future_bars=trade_bars[bar_index + 1 :],
                    risk=risk,
                    reward_risk=reward_risk,
                )
                if trade is not None:
                    trades.append(trade)
                break
    return trades


def scan_impulse_continuation(
    *,
    data: ResearchData,
    impulse_bars: int,
    impulse_atr_multiplier: float,
    reward_risk: float,
    setup: str,
) -> list[TradeCandidate]:
    """Enter after M5 impulse in the 1H trend direction."""

    trades: list[TradeCandidate] = []
    for day, day_bars in data.bars_by_day.items():
        trade_bars = bars_between(day_bars, day, 5, 22)
        if len(trade_bars) <= impulse_bars + 1:
            continue
        for bar_index in range(impulse_bars, len(trade_bars) - 1):
            bar = trade_bars[bar_index]
            side, context_atr = context_side_and_atr(data, bar.timestamp)
            if side == 0 or not math.isfinite(context_atr) or context_atr <= 0.0:
                continue
            start_bar = trade_bars[bar_index - impulse_bars]
            impulse = (bar.close - start_bar.close) * float(side)
            if impulse < context_atr * impulse_atr_multiplier:
                continue
            if side == 1 and bar.close <= bar.open:
                continue
            if side == -1 and bar.close >= bar.open:
                continue
            risk = context_atr * 1.5
            trade = simulate_exit(
                setup=setup,
                side=side,
                entry_bar=bar,
                future_bars=trade_bars[bar_index + 1 :],
                risk=risk,
                reward_risk=reward_risk,
            )
            if trade is not None:
                trades.append(trade)
            break
    return trades


def bars_between(
    bars: tuple[ResearchBar, ...],
    day_start: datetime,
    start_hour: int,
    end_hour: int,
) -> tuple[ResearchBar, ...]:
    """Return bars between two UTC hours on one day."""

    start = day_start + timedelta(hours=start_hour)
    end = day_start + timedelta(hours=end_hour)
    return tuple(bar for bar in bars if start <= bar.timestamp <= end)


def context_side_and_atr(data: ResearchData, timestamp: datetime) -> tuple[int, float]:
    """Return 1H EMA trend side and ATR available at timestamp."""

    context_index = bisect_right(data.hour_timestamps, timestamp) - 1
    if context_index < 20:
        return 0, math.nan
    context_bar = data.hour_bars[context_index]
    ema_value = data.hour_ema[context_index]
    side = 1 if context_bar.close > ema_value else -1 if context_bar.close < ema_value else 0
    return side, data.hour_atr[context_index]


def simulate_exit(
    *,
    setup: str,
    side: int,
    entry_bar: ResearchBar,
    future_bars: tuple[ResearchBar, ...],
    risk: float,
    reward_risk: float,
) -> TradeCandidate | None:
    """Simulate stop/target/time exit for one setup."""

    if risk <= 0.0 or not math.isfinite(risk):
        return None
    entry_price = entry_bar.close + (float(side) * entry_bar.spread / 2.0)
    stop_loss = entry_price - (float(side) * risk)
    take_profit = entry_price + (float(side) * risk * reward_risk)
    exit_price: float | None = None
    exit_timestamp: datetime | None = None
    exit_reason = "time"

    for bar in future_bars:
        if side == 1:
            if bar.low <= stop_loss:
                exit_price = stop_loss - (bar.spread / 2.0)
                exit_timestamp = bar.timestamp
                exit_reason = "stop_loss"
                break
            if bar.high >= take_profit:
                exit_price = take_profit - (bar.spread / 2.0)
                exit_timestamp = bar.timestamp
                exit_reason = "take_profit"
                break
            exit_price = bar.close - (bar.spread / 2.0)
        else:
            if bar.high >= stop_loss:
                exit_price = stop_loss + (bar.spread / 2.0)
                exit_timestamp = bar.timestamp
                exit_reason = "stop_loss"
                break
            if bar.low <= take_profit:
                exit_price = take_profit + (bar.spread / 2.0)
                exit_timestamp = bar.timestamp
                exit_reason = "take_profit"
                break
            exit_price = bar.close + (bar.spread / 2.0)
        exit_timestamp = bar.timestamp

    if exit_price is None or exit_timestamp is None:
        return None
    pnl = (exit_price - entry_price) * float(side)
    return TradeCandidate(
        setup=setup,
        entry_timestamp=entry_bar.timestamp,
        exit_timestamp=exit_timestamp,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        risk_per_unit=risk,
        pnl=pnl,
        realized_r=pnl / risk,
        exit_reason=exit_reason,
    )


def summarize_trades(*, setup: str, trades: tuple[TradeCandidate, ...]) -> StructuralSetupResult:
    """Summarize setup trades."""

    pnl_values = tuple(trade.pnl for trade in trades)
    monthly = monthly_pnl(trades)
    monthly_values = tuple(monthly.values())
    return StructuralSetupResult(
        setup=setup.split(":", 1)[0],
        parameters=setup,
        trades=len(trades),
        win_rate=sum(pnl > 0.0 for pnl in pnl_values) / float(len(pnl_values)),
        profit_factor=profit_factor(pnl_values),
        net_pnl=sum(pnl_values),
        max_drawdown=max_drawdown(pnl_values),
        average_r=sum(trade.realized_r for trade in trades) / float(len(trades)),
        average_monthly_pnl=sum(monthly_values) / float(len(monthly_values)),
        worst_monthly_pnl=min(monthly_values),
        best_monthly_pnl=max(monthly_values),
        positive_months=sum(value > 0.0 for value in monthly_values),
        total_months=len(monthly_values),
    )


def monthly_pnl(trades: tuple[TradeCandidate, ...]) -> dict[str, float]:
    """Group trade PnL by exit month."""

    result: defaultdict[str, float] = defaultdict(float)
    for trade in trades:
        result[f"{trade.exit_timestamp.year}-{trade.exit_timestamp.month:02d}"] += trade.pnl
    return dict(sorted(result.items()))


def profit_factor(values: tuple[float, ...]) -> float:
    """Calculate profit factor."""

    gross_profit = sum(value for value in values if value > 0.0)
    gross_loss = abs(sum(value for value in values if value < 0.0))
    if gross_loss == 0.0:
        return math.inf if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def max_drawdown(values: tuple[float, ...]) -> float:
    """Calculate trade-sequence drawdown."""

    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def write_results(path: Path, rows: list[StructuralSetupResult]) -> None:
    """Write structural scan results to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "setup",
                "parameters",
                "trades",
                "win_rate",
                "profit_factor",
                "net_pnl",
                "max_drawdown",
                "average_r",
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
                    row.setup,
                    row.parameters,
                    row.trades,
                    row.win_rate,
                    row.profit_factor,
                    row.net_pnl,
                    row.max_drawdown,
                    row.average_r,
                    row.average_monthly_pnl,
                    row.worst_monthly_pnl,
                    row.best_monthly_pnl,
                    row.positive_months,
                    row.total_months,
                ]
            )


def format_top_results(rows: list[StructuralSetupResult], *, limit: int = 10) -> str:
    """Format top structural scan results."""

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


def format_float(value: float) -> str:
    """Format float research metrics compactly."""

    if math.isinf(value):
        return "inf"
    return f"{value:.6f}".rstrip("0").rstrip(".")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Scan deterministic structural XAU/USD setups.")
    parser.add_argument("--data", required=True, type=Path, help="Real 5-minute CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/structural-setup-scan.csv"),
        type=Path,
        help="CSV output path.",
    )
    parser.add_argument("--top", default=15, type=int, help="Rows to print.")
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_research_data(args.data)
    rows = scan_structural_setups(data)
    write_results(args.output, rows)
    print(format_top_results(rows, limit=args.top))
    print(f"saved structural scan: {args.output}")


if __name__ == "__main__":
    main()
