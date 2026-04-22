"""Validate the current real-data baseline on broker historical data."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from aurus.backtest.run_real_baseline import (
    current_best_real_backtest_config,
    current_best_real_config,
)
from aurus.backtest.validation import (
    RealDataValidationReport,
    ValidationMetrics,
    evaluate_demo_readiness,
    run_real_data_validation,
)
from aurus.data import load_real_xauusd_5m_csv
from aurus.ops.summary import format_decimal


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Validate the current real-data baseline.")
    parser.add_argument("--data", required=True, type=Path, help="Canonical real 5m CSV path.")
    parser.add_argument(
        "--walk-forward-days",
        default=30,
        type=int,
        help="Non-overlapping walk-forward window size.",
    )
    parser.add_argument(
        "--output",
        default=Path("artifacts/real-baseline-validation.csv"),
        type=Path,
        help="CSV artifact path for full/segment/walk-forward metrics.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_real_xauusd_5m_csv(args.data)
    report = run_real_data_validation(
        data=data,
        strategy_config=current_best_real_config(),
        backtest_config=current_best_real_backtest_config(),
        walk_forward_days=args.walk_forward_days,
    )
    write_validation_csv(args.output, report)
    print(format_validation_report(report))
    print(f"saved validation metrics: {args.output}")


def write_validation_csv(path: Path, report: RealDataValidationReport) -> None:
    """Persist validation metrics as deterministic CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [report.full_sample, *report.segments, *report.walk_forward]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "label",
                "start",
                "end",
                "bars",
                "trades",
                "win_rate",
                "profit_factor",
                "max_drawdown",
                "net_pnl",
            ),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(validation_row(row))


def validation_row(row: ValidationMetrics) -> dict[str, str]:
    """Convert validation metrics to a stable CSV row."""

    return {
        "label": row.label,
        "start": row.start.isoformat(),
        "end": row.end.isoformat(),
        "bars": str(row.bars),
        "trades": str(row.trades),
        "win_rate": str(row.win_rate),
        "profit_factor": format_decimal(row.profit_factor),
        "max_drawdown": str(row.max_drawdown),
        "net_pnl": str(row.net_pnl),
    }


def format_validation_report(report: RealDataValidationReport) -> str:
    """Render a concise validation report."""

    readiness = evaluate_demo_readiness(report)
    profitable_windows = sum(1 for row in report.walk_forward if row.net_pnl > Decimal("0"))
    positive_pf_windows = sum(
        1
        for row in report.walk_forward
        if row.profit_factor is not None and row.profit_factor > Decimal("1")
    )
    lines = [
        "Aurus real-data validation",
        "",
        "Full sample",
        format_metrics(report.full_sample),
        "",
        "Chronological segments",
    ]
    lines.extend(format_metrics(row) for row in report.segments)
    lines.extend(
        [
            "",
            "Walk-forward windows",
            f"windows: {len(report.walk_forward)}",
            f"profitable windows: {profitable_windows}",
            f"PF>1 windows: {positive_pf_windows}",
            "",
            "Spread/slippage diagnostics",
            f"bars with spread: {report.spread_costs.bars_with_spread}",
            f"median spread: {report.spread_costs.median_spread}",
            f"p95 spread: {report.spread_costs.p95_spread}",
            f"max spread: {report.spread_costs.max_spread}",
            f"bars above strategy max spread: {report.spread_costs.bars_above_strategy_max_spread}",
            f"pct above strategy max spread: {report.spread_costs.pct_above_strategy_max_spread}",
            f"configured entry slippage: {report.spread_costs.configured_entry_slippage}",
            f"configured exit slippage: {report.spread_costs.configured_exit_slippage}",
            "",
            "Gap policy",
            f"expected closure gaps: {report.gap_policy.expected_closure_gaps}",
            f"unexpected gaps: {report.gap_policy.unexpected_gaps}",
            f"expected missing bars: {report.gap_policy.expected_missing_bars}",
            f"unexpected missing bars: {report.gap_policy.unexpected_missing_bars}",
            f"active unexpected gaps: {report.active_gap_policy.unexpected_gaps}",
            f"active unexpected missing bars: {report.active_gap_policy.unexpected_missing_bars}",
            "",
            "Demo readiness",
            f"ready: {readiness.ready}",
            "blockers: " + _format_items(readiness.blockers),
            "warnings: " + _format_items(readiness.warnings),
        ]
    )
    return "\n".join(lines)


def format_metrics(row: ValidationMetrics) -> str:
    """Render one metrics row."""

    return (
        f"{row.label}: trades={row.trades} win_rate={row.win_rate} "
        f"PF={format_decimal(row.profit_factor)} max_dd={row.max_drawdown} "
        f"net_pnl={row.net_pnl}"
    )


def _format_items(items: tuple[str, ...]) -> str:
    return "none" if not items else " | ".join(items)


if __name__ == "__main__":
    main()
