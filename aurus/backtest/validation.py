"""Validation helpers for real-data baseline research."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.types import BacktestConfig
from aurus.common.schemas import BarEvent
from aurus.data import IngestedMarketData, aggregate_closed_hourly_bars, classify_xauusd_gaps
from aurus.data.gap_policy import GapPolicyReport
from aurus.data.quality import MissingBarGap
from aurus.data.sessions import TradingSession, tag_session
from aurus.ops.metrics import calculate_metrics
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy


@dataclass(frozen=True)
class ValidationMetrics:
    """Metrics for one validation run."""

    label: str
    start: datetime
    end: datetime
    bars: int
    trades: int
    win_rate: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    net_pnl: Decimal


@dataclass(frozen=True)
class ValidationWindow:
    """Chronological execution-bar window."""

    label: str
    start: datetime
    end: datetime
    bars: tuple[BarEvent, ...]


@dataclass(frozen=True)
class SpreadCostReport:
    """Observed spread distribution compared with configured assumptions."""

    bars_with_spread: int
    min_spread: Decimal
    median_spread: Decimal
    p95_spread: Decimal
    max_spread: Decimal
    bars_above_strategy_max_spread: int
    strategy_max_spread: Decimal
    configured_entry_slippage: Decimal
    configured_exit_slippage: Decimal

    @property
    def pct_above_strategy_max_spread(self) -> Decimal:
        """Percentage of observed bars above the strategy spread threshold."""

        if self.bars_with_spread == 0:
            return Decimal("0")
        return Decimal(self.bars_above_strategy_max_spread) / Decimal(self.bars_with_spread)


@dataclass(frozen=True)
class RealDataValidationReport:
    """Complete validation report for a real-data baseline run."""

    full_sample: ValidationMetrics
    segments: tuple[ValidationMetrics, ...]
    walk_forward: tuple[ValidationMetrics, ...]
    spread_costs: SpreadCostReport
    gap_policy: GapPolicyReport
    active_gap_policy: GapPolicyReport


@dataclass(frozen=True)
class ReadinessGateConfig:
    """Explicit thresholds for demo-forward readiness checks."""

    require_no_active_unexpected_gaps: bool = True
    require_full_sample_positive: bool = True
    require_all_segments_positive: bool = True
    require_all_walk_forward_positive: bool = True
    max_spread_breach_rate: Decimal = Decimal("0.01")


@dataclass(frozen=True)
class ReadinessDecision:
    """Deterministic go/no-go result for demo-forward operation."""

    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def run_real_data_validation(
    *,
    data: IngestedMarketData,
    strategy_config: BaselineStrategyConfig,
    backtest_config: BacktestConfig,
    walk_forward_days: int = 30,
) -> RealDataValidationReport:
    """Run full-sample, segment, walk-forward, cost, and gap validation."""

    full_window = ValidationWindow(
        label="full",
        start=data.execution_bars[0].timestamp,
        end=data.execution_bars[-1].timestamp,
        bars=tuple(data.execution_bars),
    )
    return RealDataValidationReport(
        full_sample=run_validation_window(
            window=full_window,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        ),
        segments=tuple(
            run_validation_window(
                window=window,
                strategy_config=strategy_config,
                backtest_config=backtest_config,
            )
            for window in chronological_segments(data.execution_bars)
        ),
        walk_forward=tuple(
            run_validation_window(
                window=window,
                strategy_config=strategy_config,
                backtest_config=backtest_config,
            )
            for window in rolling_windows(data.execution_bars, window_days=walk_forward_days)
        ),
        spread_costs=spread_cost_report(
            data.execution_bars,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        ),
        gap_policy=classify_xauusd_gaps(data.report.missing_gaps),
        active_gap_policy=classify_xauusd_gaps(
            active_strategy_gaps(data.report.missing_gaps, strategy_config)
        ),
    )


def evaluate_demo_readiness(
    report: RealDataValidationReport,
    *,
    config: ReadinessGateConfig | None = None,
) -> ReadinessDecision:
    """Evaluate whether current evidence is sufficient for demo-forward operation."""

    gate_config = config or ReadinessGateConfig()
    blockers: list[str] = []
    warnings: list[str] = []

    if (
        gate_config.require_no_active_unexpected_gaps
        and report.active_gap_policy.has_unexpected_gaps
    ):
        blockers.append(
            "unexpected data gaps affect active strategy trading windows"
        )
    elif report.gap_policy.has_unexpected_gaps:
        warnings.append(
            "unexpected data gaps exist outside active strategy trading windows: "
            f"{report.gap_policy.unexpected_gaps}"
        )

    if gate_config.require_full_sample_positive and not _positive_sample(report.full_sample):
        blockers.append("full-sample net PnL and profit factor are not both positive")

    if gate_config.require_all_segments_positive:
        failed_segments = tuple(
            row.label for row in report.segments if not _positive_sample(row)
        )
        if failed_segments:
            blockers.append(
                "chronological segment failure: " + ", ".join(failed_segments)
            )

    if gate_config.require_all_walk_forward_positive:
        failed_windows = tuple(
            row.label for row in report.walk_forward if not _positive_sample(row)
        )
        if failed_windows:
            blockers.append(
                f"{len(failed_windows)} walk-forward windows failed positivity gates"
            )

    spread_breach_rate = report.spread_costs.pct_above_strategy_max_spread
    if spread_breach_rate > gate_config.max_spread_breach_rate:
        blockers.append(
            "spread breach rate exceeds readiness threshold: "
            f"{spread_breach_rate} > {gate_config.max_spread_breach_rate}"
        )
    elif report.spread_costs.bars_above_strategy_max_spread > 0:
        warnings.append(
            "some bars exceeded the strategy spread limit: "
            f"{report.spread_costs.bars_above_strategy_max_spread}"
        )

    return ReadinessDecision(
        ready=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def run_validation_window(
    *,
    window: ValidationWindow,
    strategy_config: BaselineStrategyConfig,
    backtest_config: BacktestConfig,
) -> ValidationMetrics:
    """Run one deterministic baseline backtest window."""

    execution_bars = list(window.bars)
    context_bars = aggregate_closed_hourly_bars(execution_bars)
    result = BacktestEngine(
        strategy=BaselineXauUsdStrategy(context_bars=context_bars, config=strategy_config),
        config=backtest_config,
    ).run(execution_bars)
    metrics = calculate_metrics(result.trades, result.equity_curve)
    return ValidationMetrics(
        label=window.label,
        start=window.start,
        end=window.end,
        bars=len(execution_bars),
        trades=metrics.trade_count,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor,
        max_drawdown=metrics.max_drawdown,
        net_pnl=metrics.total_pnl,
    )


def chronological_segments(bars: Sequence[BarEvent]) -> tuple[ValidationWindow, ...]:
    """Split bars into early/mid/late chronological thirds."""

    ordered = tuple(sorted(bars, key=lambda bar: bar.timestamp))
    if not ordered:
        return ()
    cut1 = len(ordered) // 3
    cut2 = (2 * len(ordered)) // 3
    parts = (
        ("early", ordered[:cut1]),
        ("mid", ordered[cut1:cut2]),
        ("late", ordered[cut2:]),
    )
    return tuple(_window_from_bars(label, part) for label, part in parts if part)


def rolling_windows(
    bars: Sequence[BarEvent],
    *,
    window_days: int,
) -> tuple[ValidationWindow, ...]:
    """Build non-overlapping chronological walk-forward windows."""

    if window_days <= 0:
        raise ValueError("window_days must be positive")
    ordered = tuple(sorted(bars, key=lambda bar: bar.timestamp))
    if not ordered:
        return ()

    windows: list[ValidationWindow] = []
    window_start = ordered[0].timestamp
    final_timestamp = ordered[-1].timestamp
    window_index = 1
    while window_start <= final_timestamp:
        window_end = window_start + timedelta(days=window_days)
        window_bars = tuple(
            bar for bar in ordered if window_start <= bar.timestamp < window_end
        )
        if window_bars:
            windows.append(_window_from_bars(f"wf-{window_index:03d}", window_bars))
            window_index += 1
        window_start = window_end
    return tuple(windows)


def spread_cost_report(
    bars: Sequence[BarEvent],
    *,
    strategy_config: BaselineStrategyConfig,
    backtest_config: BacktestConfig,
) -> SpreadCostReport:
    """Compare observed broker spreads with configured spread/slippage assumptions."""

    spreads = sorted(bar.spread for bar in bars if bar.spread is not None)
    if not spreads:
        return SpreadCostReport(
            bars_with_spread=0,
            min_spread=Decimal("0"),
            median_spread=Decimal("0"),
            p95_spread=Decimal("0"),
            max_spread=Decimal("0"),
            bars_above_strategy_max_spread=0,
            strategy_max_spread=strategy_config.max_spread,
            configured_entry_slippage=backtest_config.entry_slippage
            or backtest_config.slippage,
            configured_exit_slippage=backtest_config.exit_slippage or backtest_config.slippage,
        )

    return SpreadCostReport(
        bars_with_spread=len(spreads),
        min_spread=spreads[0],
        median_spread=_quantile(spreads, Decimal("0.50")),
        p95_spread=_quantile(spreads, Decimal("0.95")),
        max_spread=spreads[-1],
        bars_above_strategy_max_spread=sum(
            1 for spread in spreads if spread > strategy_config.max_spread
        ),
        strategy_max_spread=strategy_config.max_spread,
        configured_entry_slippage=backtest_config.entry_slippage or backtest_config.slippage,
        configured_exit_slippage=backtest_config.exit_slippage or backtest_config.slippage,
    )


def active_strategy_gaps(
    gaps: Sequence[MissingBarGap],
    strategy_config: BaselineStrategyConfig,
) -> tuple[MissingBarGap, ...]:
    """Return gaps with missing timestamps inside the strategy's active windows."""

    return tuple(
        gap
        for gap in gaps
        if any(
            _is_active_strategy_timestamp(timestamp, strategy_config)
            for timestamp in gap.missing_timestamps
        )
    )


def _window_from_bars(label: str, bars: Sequence[BarEvent]) -> ValidationWindow:
    ordered = tuple(sorted(bars, key=lambda bar: bar.timestamp))
    return ValidationWindow(
        label=label,
        start=ordered[0].timestamp,
        end=ordered[-1].timestamp,
        bars=ordered,
    )


def _quantile(values: Sequence[Decimal], quantile: Decimal) -> Decimal:
    if not values:
        return Decimal("0")
    index = int((Decimal(len(values) - 1) * quantile).to_integral_value())
    return values[index]


def _positive_sample(row: ValidationMetrics) -> bool:
    return (
        row.net_pnl > Decimal("0")
        and row.profit_factor is not None
        and row.profit_factor > Decimal("1")
    )


def _is_active_strategy_timestamp(
    timestamp: datetime,
    strategy_config: BaselineStrategyConfig,
) -> bool:
    session = tag_session(timestamp)
    if session.value not in strategy_config.allowed_sessions:
        return False
    if session == TradingSession.LONDON:
        return _london_subwindow(timestamp) in strategy_config.allowed_london_subwindows
    if session == TradingSession.NEW_YORK:
        return timestamp.hour < strategy_config.early_new_york_end_hour_utc
    return True


def _london_subwindow(timestamp: datetime) -> str:
    if 7 <= timestamp.hour < 9:
        return "open"
    if 9 <= timestamp.hour < 11:
        return "mid"
    if 11 <= timestamp.hour < 13:
        return "late"
    return "outside_london"
