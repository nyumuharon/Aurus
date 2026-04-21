"""Completed-trade cohort analysis for the baseline XAU/USD strategy."""

from __future__ import annotations

import argparse
import csv
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig, TradeRecord
from aurus.common.schemas import BarEvent, SignalEvent
from aurus.data import TradingSession, aggregate_closed_hourly_bars, load_real_xauusd_5m_csv
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy

LOGGER = logging.getLogger(__name__)

PULLBACK_BUCKETS = (
    (Decimal("0"), Decimal("0.10"), "0.00-0.10"),
    (Decimal("0.10"), Decimal("0.25"), "0.10-0.25"),
    (Decimal("0.25"), Decimal("0.50"), "0.25-0.50"),
    (Decimal("0.50"), Decimal("0.75"), "0.50-0.75"),
    (Decimal("0.75"), None, "0.75+"),
)


@dataclass(frozen=True)
class EntryContext:
    """Signal and bar context captured at entry."""

    signal: SignalEvent
    previous_bar: BarEvent
    entry_bar: BarEvent


@dataclass(frozen=True)
class TradeFeatureRow:
    """One enriched completed-trade analysis row."""

    entry_timestamp: datetime
    exit_timestamp: datetime
    direction: str
    realized_r: Decimal
    pnl: Decimal
    outcome: str
    pullback_depth_atr: Decimal
    trend_strength: Decimal
    atr_strength: Decimal
    spread: Decimal | None
    london_subwindow: str
    pre_entry_extension_atr: Decimal
    segment: str


@dataclass(frozen=True)
class CohortStats:
    """Aggregate performance statistics for one cohort."""

    cohort: str
    trades: int
    win_rate: Decimal
    profit_factor: Decimal | None
    average_r: Decimal
    net_pnl: Decimal
    max_drawdown: Decimal
    full_loss_pct: Decimal
    breakeven_pct: Decimal
    partial_lock_pct: Decimal
    full_tp_pct: Decimal


class RecordingStrategy:
    """Wrap a strategy and retain signal context for completed-trade analysis."""

    def __init__(self, inner: BaselineXauUsdStrategy) -> None:
        self.inner = inner
        self.entries: dict[tuple[datetime, str], EntryContext] = {}

    def __call__(self, bars: Sequence[BarEvent]) -> list[SignalEvent]:
        signals = self.inner(bars)
        if len(bars) < 2:
            return signals

        previous_bar = bars[-2]
        entry_bar = bars[-1]
        for signal in signals:
            self.entries[(signal.timestamp, str(signal.side))] = EntryContext(
                signal=signal,
                previous_bar=previous_bar,
                entry_bar=entry_bar,
            )
        return signals


def current_best_analysis_config() -> BaselineStrategyConfig:
    """Return the current best baseline config without pullback-depth filtering."""

    return BaselineStrategyConfig(
        reward_risk=Decimal("1.25"),
        min_atr=Decimal("0.75"),
        min_atr_strength=Decimal("0.0005"),
        min_trend_strength=Decimal("0.0002"),
        min_pullback_depth_atr=Decimal("0"),
        context_ema_period=3,
        execution_ema_period=5,
        max_spread=Decimal("0.50"),
        confirmation_mode="relaxed",
        entry_mode="baseline",
        allowed_sessions=frozenset({TradingSession.LONDON.value}),
    )


def current_best_backtest_config() -> BacktestConfig:
    """Return the current best stop-tightening assumptions."""

    return BacktestConfig(
        record_events=False,
        stop_tightening_enabled=True,
        breakeven_trigger_r=Decimal("0.25"),
        trailing_trigger_r=Decimal("0.75"),
        trailing_stop_r=Decimal("0.50"),
    )


def run_feature_analysis(data_path: Path) -> list[TradeFeatureRow]:
    """Run the current baseline and return enriched completed-trade rows."""

    data = load_real_xauusd_5m_csv(data_path)
    context_bars = aggregate_closed_hourly_bars(data.execution_bars)
    recorder = RecordingStrategy(
        BaselineXauUsdStrategy(
            context_bars=context_bars,
            config=current_best_analysis_config(),
        )
    )
    result = BacktestEngine(
        strategy=recorder,
        config=current_best_backtest_config(),
    ).run(data.execution_bars)
    return build_trade_feature_rows(
        trades=result.trades,
        entries=recorder.entries,
        segmenter=chronological_segmenter(data.execution_bars),
    )


def build_trade_feature_rows(
    *,
    trades: tuple[TradeRecord, ...],
    entries: dict[tuple[datetime, str], EntryContext],
    segmenter: Callable[[datetime], str],
) -> list[TradeFeatureRow]:
    """Join closed trades to their entry signal features."""

    rows: list[TradeFeatureRow] = []
    for trade in trades:
        context = entries.get((trade.entry_timestamp, str(trade.side)))
        if context is None:
            raise RuntimeError(f"missing signal context for trade {trade.trade_id}")
        rows.append(row_from_trade(trade=trade, context=context, segmenter=segmenter))
    return rows


def row_from_trade(
    *,
    trade: TradeRecord,
    context: EntryContext,
    segmenter: Callable[[datetime], str],
) -> TradeFeatureRow:
    """Build one enriched analysis row from a closed trade."""

    risk_per_unit = actual_risk_per_unit(trade=trade, context=context)
    realized_r = trade.net_pnl / (risk_per_unit * trade.quantity)
    return TradeFeatureRow(
        entry_timestamp=trade.entry_timestamp,
        exit_timestamp=trade.exit_timestamp,
        direction=str(trade.side),
        realized_r=realized_r,
        pnl=trade.net_pnl,
        outcome=classify_outcome(trade=trade, realized_r=realized_r),
        pullback_depth_atr=decimal_feature(context.signal, "pullback_depth_atr"),
        trend_strength=decimal_feature(context.signal, "trend_strength"),
        atr_strength=decimal_feature(context.signal, "atr_strength"),
        spread=context.entry_bar.spread,
        london_subwindow=london_subwindow(context.entry_bar.timestamp),
        pre_entry_extension_atr=pre_entry_extension_atr(context),
        segment=segmenter(trade.entry_timestamp),
    )


def actual_risk_per_unit(*, trade: TradeRecord, context: EntryContext) -> Decimal:
    """Calculate initial executed risk from actual fill and signal stop."""

    stop_loss = decimal_feature(context.signal, "stop_loss")
    risk = abs(trade.entry_price - stop_loss)
    if risk <= Decimal("0"):
        return decimal_feature(context.signal, "risk_per_unit")
    return risk


def decimal_feature(signal: SignalEvent, name: str) -> Decimal:
    """Read a Decimal-valued signal feature."""

    value = signal.features.get(name)
    if value is None:
        raise RuntimeError(f"missing signal feature: {name}")
    return Decimal(str(value))


def pre_entry_extension_atr(context: EntryContext) -> Decimal:
    """Return directionally signed entry close extension from EMA, normalized by ATR."""

    ema_value = decimal_feature(context.signal, "ema20")
    atr_value = decimal_feature(context.signal, "atr")
    if atr_value <= Decimal("0"):
        return Decimal("0")
    if str(context.signal.side) == "buy":
        return (context.entry_bar.close - ema_value) / atr_value
    return (ema_value - context.entry_bar.close) / atr_value


def classify_outcome(*, trade: TradeRecord, realized_r: Decimal) -> str:
    """Classify outcomes from realized R and backtest exit reason."""

    if trade.exit_reason == "take_profit":
        return "full TP"
    if abs(realized_r) <= Decimal("0.05"):
        return "breakeven"
    if realized_r > Decimal("0.05"):
        return "partial lock"
    return "full loss"


def london_subwindow(timestamp: datetime) -> str:
    """Bucket London timestamps into simple UTC subwindows."""

    if 7 <= timestamp.hour < 9:
        return "open"
    if 9 <= timestamp.hour < 11:
        return "mid"
    if 11 <= timestamp.hour < 13:
        return "late"
    return "outside_london"


def chronological_segmenter(bars: list[BarEvent]) -> Callable[[datetime], str]:
    """Return a deterministic early/mid/late segment function."""

    ordered_bars = sorted(bars, key=lambda bar: bar.timestamp)
    cut1 = len(ordered_bars) // 3
    cut2 = (2 * len(ordered_bars)) // 3
    early_end = ordered_bars[cut1 - 1].timestamp
    mid_end = ordered_bars[cut2 - 1].timestamp

    def segment(timestamp: datetime) -> str:
        if timestamp <= early_end:
            return "early"
        if timestamp <= mid_end:
            return "mid"
        return "late"

    return segment


def pullback_bucket(value: Decimal) -> str:
    """Bucket pullback depth into fixed ATR-normalized ranges."""

    for lower, upper, label in PULLBACK_BUCKETS:
        if upper is None and value >= lower:
            return label
        if upper is not None and lower <= value < upper:
            return label
    return PULLBACK_BUCKETS[0][2]


def quantile_bucket(
    *,
    value: Decimal,
    low_cutoff: Decimal,
    high_cutoff: Decimal,
    labels: tuple[str, str, str],
) -> str:
    """Assign low/mid/high quantile buckets from precomputed cutoffs."""

    if value <= low_cutoff:
        return labels[0]
    if value <= high_cutoff:
        return labels[1]
    return labels[2]


def quantile_cutoffs(values: Iterable[Decimal]) -> tuple[Decimal, Decimal]:
    """Return deterministic tertile cutoffs."""

    ordered = sorted(values)
    if not ordered:
        return Decimal("0"), Decimal("0")
    low_index = max(0, (len(ordered) // 3) - 1)
    high_index = max(0, ((2 * len(ordered)) // 3) - 1)
    return ordered[low_index], ordered[high_index]


def cohort_stats(cohort: str, rows: Sequence[TradeFeatureRow]) -> CohortStats:
    """Aggregate rows into one performance cohort."""

    if not rows:
        return CohortStats(
            cohort=cohort,
            trades=0,
            win_rate=Decimal("0"),
            profit_factor=None,
            average_r=Decimal("0"),
            net_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            full_loss_pct=Decimal("0"),
            breakeven_pct=Decimal("0"),
            partial_lock_pct=Decimal("0"),
            full_tp_pct=Decimal("0"),
        )

    profits = [row.pnl for row in rows if row.pnl > Decimal("0")]
    losses = [row.pnl for row in rows if row.pnl < Decimal("0")]
    gross_profit = sum(profits, Decimal("0"))
    gross_loss = abs(sum(losses, Decimal("0")))
    outcomes = Counter(row.outcome for row in rows)
    total = Decimal(len(rows))
    ordered_rows = sorted(rows, key=lambda row: row.entry_timestamp)
    return CohortStats(
        cohort=cohort,
        trades=len(rows),
        win_rate=Decimal(sum(1 for row in rows if row.pnl > Decimal("0"))) / total,
        profit_factor=None if gross_loss == Decimal("0") else gross_profit / gross_loss,
        average_r=sum((row.realized_r for row in rows), Decimal("0")) / total,
        net_pnl=sum((row.pnl for row in rows), Decimal("0")),
        max_drawdown=max_pnl_drawdown(ordered_rows),
        full_loss_pct=Decimal(outcomes["full loss"]) / total,
        breakeven_pct=Decimal(outcomes["breakeven"]) / total,
        partial_lock_pct=Decimal(outcomes["partial lock"]) / total,
        full_tp_pct=Decimal(outcomes["full TP"]) / total,
    )


def max_pnl_drawdown(rows: Sequence[TradeFeatureRow]) -> Decimal:
    """Calculate max drawdown from cumulative cohort PnL."""

    equity = Decimal("0")
    peak = Decimal("0")
    drawdown = Decimal("0")
    for row in rows:
        equity += row.pnl
        if equity > peak:
            peak = equity
        current_drawdown = peak - equity
        if current_drawdown > drawdown:
            drawdown = current_drawdown
    return drawdown


def grouped_stats(
    rows: Sequence[TradeFeatureRow],
    key: Callable[[TradeFeatureRow], str],
) -> list[CohortStats]:
    """Return stats grouped by a row key."""

    groups: dict[str, list[TradeFeatureRow]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return [cohort_stats(name, groups[name]) for name in sorted(groups)]


def interaction_stats(
    rows: Sequence[TradeFeatureRow],
    left_key: Callable[[TradeFeatureRow], str],
    right_key: Callable[[TradeFeatureRow], str],
) -> list[CohortStats]:
    """Return stats for 2D interaction cohorts."""

    return grouped_stats(rows, lambda row: f"{left_key(row)} x {right_key(row)}")


def write_trade_rows(rows: Sequence[TradeFeatureRow], path: Path) -> None:
    """Persist enriched trade rows."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entry_timestamp",
                "exit_timestamp",
                "direction",
                "realized_r",
                "pnl",
                "outcome",
                "pullback_depth_atr",
                "trend_strength",
                "atr_strength",
                "spread",
                "london_subwindow",
                "pre_entry_extension_atr",
                "segment",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "entry_timestamp": row.entry_timestamp.isoformat(),
                    "exit_timestamp": row.exit_timestamp.isoformat(),
                    "direction": row.direction,
                    "realized_r": str(row.realized_r),
                    "pnl": str(row.pnl),
                    "outcome": row.outcome,
                    "pullback_depth_atr": str(row.pullback_depth_atr),
                    "trend_strength": str(row.trend_strength),
                    "atr_strength": str(row.atr_strength),
                    "spread": "" if row.spread is None else str(row.spread),
                    "london_subwindow": row.london_subwindow,
                    "pre_entry_extension_atr": str(row.pre_entry_extension_atr),
                    "segment": row.segment,
                }
            )


def write_stats(rows: Sequence[CohortStats], path: Path) -> None:
    """Persist cohort stats."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "cohort",
                "trades",
                "win_rate",
                "profit_factor",
                "average_r",
                "net_pnl",
                "max_drawdown",
                "full_loss_pct",
                "breakeven_pct",
                "partial_lock_pct",
                "full_tp_pct",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "cohort": row.cohort,
                    "trades": row.trades,
                    "win_rate": str(row.win_rate),
                    "profit_factor": "" if row.profit_factor is None else str(row.profit_factor),
                    "average_r": str(row.average_r),
                    "net_pnl": str(row.net_pnl),
                    "max_drawdown": str(row.max_drawdown),
                    "full_loss_pct": str(row.full_loss_pct),
                    "breakeven_pct": str(row.breakeven_pct),
                    "partial_lock_pct": str(row.partial_lock_pct),
                    "full_tp_pct": str(row.full_tp_pct),
                }
            )


def build_all_tables(rows: Sequence[TradeFeatureRow]) -> dict[str, list[CohortStats]]:
    """Build all requested cohort tables."""

    trend_low, trend_high = quantile_cutoffs(row.trend_strength for row in rows)
    extension_low, extension_high = quantile_cutoffs(row.pre_entry_extension_atr for row in rows)
    trend_bucket = lambda row: quantile_bucket(  # noqa: E731
        value=row.trend_strength,
        low_cutoff=trend_low,
        high_cutoff=trend_high,
        labels=("trend_low", "trend_mid", "trend_high"),
    )
    extension_bucket = lambda row: quantile_bucket(  # noqa: E731
        value=row.pre_entry_extension_atr,
        low_cutoff=extension_low,
        high_cutoff=extension_high,
        labels=("extension_low", "extension_mid", "extension_high"),
    )

    tables: dict[str, list[CohortStats]] = {
        "pullback_buckets": grouped_stats(
            rows,
            lambda row: pullback_bucket(row.pullback_depth_atr),
        ),
        "pullback_x_trend": interaction_stats(
            rows,
            lambda row: pullback_bucket(row.pullback_depth_atr),
            trend_bucket,
        ),
        "pullback_x_london": interaction_stats(
            rows,
            lambda row: pullback_bucket(row.pullback_depth_atr),
            lambda row: row.london_subwindow,
        ),
        "pullback_x_extension": interaction_stats(
            rows,
            lambda row: pullback_bucket(row.pullback_depth_atr),
            extension_bucket,
        ),
    }
    for segment in ("early", "mid", "late"):
        segment_rows = [row for row in rows if row.segment == segment]
        tables[f"pullback_buckets_{segment}"] = grouped_stats(
            segment_rows,
            lambda row: pullback_bucket(row.pullback_depth_atr),
        )
    return tables


def write_all_artifacts(rows: Sequence[TradeFeatureRow], output_dir: Path) -> dict[str, Path]:
    """Write trade rows and all cohort tables to CSV artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    trade_rows_path = output_dir / "trade-features.csv"
    write_trade_rows(rows, trade_rows_path)
    paths["trade_features"] = trade_rows_path

    for name, table in build_all_tables(rows).items():
        path = output_dir / f"{name}.csv"
        write_stats(table, path)
        paths[name] = path
    return paths


def format_stats_table(rows: Sequence[CohortStats], *, include_outcomes: bool) -> str:
    """Render a compact markdown stats table."""

    headers = ["cohort", "trades", "win_rate", "PF", "avg_R", "net_PnL"]
    if include_outcomes:
        headers.extend(["loss%", "BE%", "lock%", "TP%"])
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        values = [
            row.cohort,
            str(row.trades),
            pct(row.win_rate),
            dec(row.profit_factor),
            dec(row.average_r),
            dec(row.net_pnl),
        ]
        if include_outcomes:
            values.extend(
                [
                    pct(row.full_loss_pct),
                    pct(row.breakeven_pct),
                    pct(row.partial_lock_pct),
                    pct(row.full_tp_pct),
                ]
            )
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def dec(value: Decimal | None) -> str:
    """Format Decimal metrics."""

    if value is None:
        return "inf"
    return f"{float(value):.4f}"


def pct(value: Decimal) -> str:
    """Format Decimal proportions."""

    return f"{float(value):.2%}"


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""

    parser = argparse.ArgumentParser(description="Run baseline trade cohort analysis.")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output-dir", default=Path("artifacts/cohort-analysis"), type=Path)
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    logging.basicConfig(level=logging.WARNING)
    rows = run_feature_analysis(args.data)
    paths = write_all_artifacts(rows, args.output_dir)
    tables = build_all_tables(rows)
    print(f"completed trades: {len(rows)}")
    print(f"trade rows: {paths['trade_features']}")
    print()
    print("Pullback depth buckets")
    print(format_stats_table(tables["pullback_buckets"], include_outcomes=True))
    print()
    print("Pullback x trend strength")
    print(format_stats_table(tables["pullback_x_trend"], include_outcomes=False))
    print()
    print("Pullback x London subwindow")
    print(format_stats_table(tables["pullback_x_london"], include_outcomes=False))
    print()
    print("Pullback x pre-entry extension")
    print(format_stats_table(tables["pullback_x_extension"], include_outcomes=False))


if __name__ == "__main__":
    main()
