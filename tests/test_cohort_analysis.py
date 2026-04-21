"""Tests for completed-trade cohort analysis helpers."""

from datetime import UTC, datetime
from decimal import Decimal

from aurus.backtest.cohort_analysis import (
    TradeFeatureRow,
    classify_outcome,
    cohort_stats,
    london_subwindow,
    pullback_bucket,
    quantile_bucket,
    quantile_cutoffs,
)
from aurus.backtest.types import TradeRecord


def make_trade(*, exit_reason: str, pnl: Decimal = Decimal("0")) -> TradeRecord:
    return TradeRecord(
        trade_id="trade-1",
        instrument="XAU/USD",
        side="buy",
        quantity=Decimal("1"),
        entry_timestamp=datetime(2026, 4, 21, 7, 0, tzinfo=UTC),
        exit_timestamp=datetime(2026, 4, 21, 7, 5, tzinfo=UTC),
        entry_price=Decimal("100"),
        exit_price=Decimal("101"),
        gross_pnl=pnl,
        commission=Decimal("0"),
        net_pnl=pnl,
        exit_reason=exit_reason,
    )


def make_row(
    index: int,
    *,
    realized_r: Decimal,
    pnl: Decimal,
    outcome: str,
) -> TradeFeatureRow:
    return TradeFeatureRow(
        entry_timestamp=datetime(2026, 4, 21, 7, index, tzinfo=UTC),
        exit_timestamp=datetime(2026, 4, 21, 7, index + 1, tzinfo=UTC),
        direction="buy",
        realized_r=realized_r,
        pnl=pnl,
        outcome=outcome,
        pullback_depth_atr=Decimal("0.25"),
        trend_strength=Decimal("0.001"),
        atr_strength=Decimal("0.001"),
        spread=Decimal("0.20"),
        london_subwindow="open",
        pre_entry_extension_atr=Decimal("0.50"),
        segment="early",
    )


def test_classify_outcome_uses_exit_reason_and_realized_r() -> None:
    assert (
        classify_outcome(trade=make_trade(exit_reason="take_profit"), realized_r=Decimal("1"))
        == "full TP"
    )
    assert (
        classify_outcome(trade=make_trade(exit_reason="stop_loss"), realized_r=Decimal("0.02"))
        == "breakeven"
    )
    assert (
        classify_outcome(trade=make_trade(exit_reason="stop_loss"), realized_r=Decimal("0.50"))
        == "partial lock"
    )
    assert (
        classify_outcome(trade=make_trade(exit_reason="stop_loss"), realized_r=Decimal("-1"))
        == "full loss"
    )


def test_london_subwindow_buckets_utc_hours() -> None:
    assert london_subwindow(datetime(2026, 4, 21, 7, 0, tzinfo=UTC)) == "open"
    assert london_subwindow(datetime(2026, 4, 21, 9, 0, tzinfo=UTC)) == "mid"
    assert london_subwindow(datetime(2026, 4, 21, 11, 0, tzinfo=UTC)) == "late"
    assert london_subwindow(datetime(2026, 4, 21, 13, 0, tzinfo=UTC)) == "outside_london"


def test_pullback_and_quantile_buckets_are_deterministic() -> None:
    assert pullback_bucket(Decimal("0")) == "0.00-0.10"
    assert pullback_bucket(Decimal("0.25")) == "0.25-0.50"
    assert pullback_bucket(Decimal("0.75")) == "0.75+"

    low, high = quantile_cutoffs(
        [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5"), Decimal("6")]
    )

    assert low == Decimal("2")
    assert high == Decimal("4")
    assert (
        quantile_bucket(
            value=Decimal("5"),
            low_cutoff=low,
            high_cutoff=high,
            labels=("low", "mid", "high"),
        )
        == "high"
    )


def test_cohort_stats_calculates_performance_and_outcomes() -> None:
    stats = cohort_stats(
        "sample",
        [
            make_row(0, realized_r=Decimal("1"), pnl=Decimal("10"), outcome="full TP"),
            make_row(1, realized_r=Decimal("-1"), pnl=Decimal("-5"), outcome="full loss"),
            make_row(2, realized_r=Decimal("0"), pnl=Decimal("0"), outcome="breakeven"),
        ],
    )

    assert stats.trades == 3
    assert stats.win_rate == Decimal("0.3333333333333333333333333333")
    assert stats.profit_factor == Decimal("2")
    assert stats.average_r == Decimal("0")
    assert stats.net_pnl == Decimal("5")
    assert stats.full_loss_pct == Decimal("0.3333333333333333333333333333")
    assert stats.breakeven_pct == Decimal("0.3333333333333333333333333333")
    assert stats.full_tp_pct == Decimal("0.3333333333333333333333333333")
