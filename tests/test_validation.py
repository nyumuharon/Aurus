"""Tests for real-data validation helpers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurus.backtest.types import BacktestConfig
from aurus.backtest.validation import (
    ReadinessGateConfig,
    RealDataValidationReport,
    SpreadCostReport,
    ValidationMetrics,
    chronological_segments,
    evaluate_demo_readiness,
    rolling_windows,
    spread_cost_report,
)
from aurus.common.schemas import BarEvent
from aurus.data.gap_policy import classify_xauusd_gaps
from aurus.data.quality import MissingBarGap
from aurus.strategy import BaselineStrategyConfig

NOW = datetime(2026, 4, 20, tzinfo=UTC)


def bar(index: int, *, spread: Decimal = Decimal("0.20")) -> BarEvent:
    timestamp = NOW + timedelta(minutes=5 * index)
    return BarEvent(
        timestamp=timestamp,
        correlation_id=f"bar-{index}",
        instrument="XAU/USD",
        timeframe="5m",
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
        spread=spread,
    )


def test_chronological_segments_split_into_thirds() -> None:
    segments = chronological_segments([bar(index) for index in range(9)])

    assert [segment.label for segment in segments] == ["early", "mid", "late"]
    assert [len(segment.bars) for segment in segments] == [3, 3, 3]
    assert segments[0].start == bar(0).timestamp
    assert segments[-1].end == bar(8).timestamp


def test_rolling_windows_build_non_overlapping_windows() -> None:
    bars = [bar(index) for index in range(12 * 24 * 3)]

    windows = rolling_windows(bars, window_days=1)

    assert len(windows) == 3
    assert [window.label for window in windows] == ["wf-001", "wf-002", "wf-003"]
    assert all(len(window.bars) == 12 * 24 for window in windows)


def test_spread_cost_report_counts_bars_above_strategy_threshold() -> None:
    report = spread_cost_report(
        [bar(0, spread=Decimal("0.10")), bar(1, spread=Decimal("0.60"))],
        strategy_config=BaselineStrategyConfig(max_spread=Decimal("0.50")),
        backtest_config=BacktestConfig(
            entry_slippage=Decimal("0.05"),
            exit_slippage=Decimal("0.10"),
        ),
    )

    assert report.bars_with_spread == 2
    assert report.bars_above_strategy_max_spread == 1
    assert report.pct_above_strategy_max_spread == Decimal("0.5")
    assert report.configured_entry_slippage == Decimal("0.05")
    assert report.configured_exit_slippage == Decimal("0.10")


def test_gap_policy_separates_weekend_and_unexpected_gaps() -> None:
    weekend_gap = MissingBarGap(
        previous_timestamp=datetime(2026, 4, 17, 21, 55, tzinfo=UTC),
        next_timestamp=datetime(2026, 4, 19, 22, 0, tzinfo=UTC),
        missing_timestamps=(datetime(2026, 4, 18, 0, 0, tzinfo=UTC),),
    )
    weekday_gap = MissingBarGap(
        previous_timestamp=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
        next_timestamp=datetime(2026, 4, 20, 10, 10, tzinfo=UTC),
        missing_timestamps=(datetime(2026, 4, 20, 10, 5, tzinfo=UTC),),
    )

    report = classify_xauusd_gaps((weekend_gap, weekday_gap))

    assert report.expected_closure_gaps == 1
    assert report.unexpected_gaps == 1
    assert report.expected_missing_bars == 1
    assert report.unexpected_missing_bars == 1
    assert report.has_unexpected_gaps is True


def validation_metrics(label: str = "sample") -> ValidationMetrics:
    return ValidationMetrics(
        label=label,
        start=NOW,
        end=NOW + timedelta(hours=1),
        bars=12,
        trades=3,
        win_rate=Decimal("0.67"),
        profit_factor=Decimal("1.50"),
        max_drawdown=Decimal("10"),
        net_pnl=Decimal("25"),
    )


def readiness_report(
    *,
    gap_report_unexpected: bool = False,
    spread_breaches: int = 0,
    failed_segment: bool = False,
) -> RealDataValidationReport:
    segment = (
        ValidationMetrics(
            label="early",
            start=NOW,
            end=NOW + timedelta(hours=1),
            bars=12,
            trades=3,
            win_rate=Decimal("0.33"),
            profit_factor=Decimal("0.80"),
            max_drawdown=Decimal("10"),
            net_pnl=Decimal("-5"),
        )
        if failed_segment
        else validation_metrics("early")
    )
    return RealDataValidationReport(
        full_sample=validation_metrics("full"),
        segments=(segment,),
        walk_forward=(validation_metrics("wf-001"),),
        spread_costs=SpreadCostReport(
            bars_with_spread=100,
            min_spread=Decimal("0.10"),
            median_spread=Decimal("0.20"),
            p95_spread=Decimal("0.30"),
            max_spread=Decimal("0.60"),
            bars_above_strategy_max_spread=spread_breaches,
            strategy_max_spread=Decimal("0.50"),
            configured_entry_slippage=Decimal("0"),
            configured_exit_slippage=Decimal("0"),
        ),
        gap_policy=classify_xauusd_gaps(
            (
                MissingBarGap(
                    previous_timestamp=NOW,
                    next_timestamp=NOW + timedelta(minutes=10),
                    missing_timestamps=(NOW + timedelta(minutes=5),),
                ),
            )
            if gap_report_unexpected
            else ()
        ),
    )


def test_readiness_passes_when_validation_is_clean() -> None:
    decision = evaluate_demo_readiness(readiness_report())

    assert decision.ready is True
    assert decision.blockers == ()
    assert decision.warnings == ()


def test_readiness_blocks_unexpected_gaps_and_failed_segments() -> None:
    decision = evaluate_demo_readiness(
        readiness_report(gap_report_unexpected=True, failed_segment=True)
    )

    assert decision.ready is False
    assert any("unexpected data gaps" in blocker for blocker in decision.blockers)
    assert any("chronological segment failure" in blocker for blocker in decision.blockers)


def test_readiness_warns_for_small_spread_breach_rate() -> None:
    decision = evaluate_demo_readiness(readiness_report(spread_breaches=1))

    assert decision.ready is True
    assert decision.warnings == ("some bars exceeded the strategy spread limit: 1",)


def test_readiness_blocks_large_spread_breach_rate() -> None:
    decision = evaluate_demo_readiness(
        readiness_report(spread_breaches=2),
        config=ReadinessGateConfig(max_spread_breach_rate=Decimal("0.01")),
    )

    assert decision.ready is False
    assert any("spread breach rate exceeds" in blocker for blocker in decision.blockers)
