"""Audit real XAU/USD CSV gaps against the current strategy trading window."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from aurus.backtest.run_real_baseline import current_best_real_config
from aurus.backtest.validation import active_strategy_gaps
from aurus.data import load_real_xauusd_5m_csv
from aurus.data.gap_policy import classify_xauusd_gaps, is_expected_xauusd_closure
from aurus.data.quality import MissingBarGap
from aurus.ops.summary import format_decimal

GAP_AUDIT_COLUMNS = (
    "previous_timestamp",
    "next_timestamp",
    "missing_bars",
    "first_missing_timestamp",
    "last_missing_timestamp",
    "expected_closure",
    "active_strategy_window",
)


def write_gap_audit_csv(
    *,
    path: Path,
    gaps: tuple[MissingBarGap, ...],
    active_gaps: tuple[MissingBarGap, ...],
) -> None:
    """Write a deterministic CSV audit of missing-bar gaps."""

    active_gap_ids = {_gap_id(gap) for gap in active_gaps}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GAP_AUDIT_COLUMNS)
        writer.writeheader()
        for gap in gaps:
            writer.writerow(gap_audit_row(gap, active_gap_ids=active_gap_ids))


def gap_audit_row(
    gap: MissingBarGap,
    *,
    active_gap_ids: set[tuple[str, str]],
) -> dict[str, str]:
    """Convert one gap to a stable CSV row."""

    return {
        "previous_timestamp": gap.previous_timestamp.isoformat(),
        "next_timestamp": gap.next_timestamp.isoformat(),
        "missing_bars": str(len(gap.missing_timestamps)),
        "first_missing_timestamp": gap.missing_timestamps[0].isoformat(),
        "last_missing_timestamp": gap.missing_timestamps[-1].isoformat(),
        "expected_closure": str(is_expected_xauusd_closure(gap)),
        "active_strategy_window": str(_gap_id(gap) in active_gap_ids),
    }


def format_gap_audit_summary(
    *,
    gaps: tuple[MissingBarGap, ...],
    active_gaps: tuple[MissingBarGap, ...],
    output: Path,
) -> str:
    """Render a concise gap audit summary."""

    total_missing = sum(len(gap.missing_timestamps) for gap in gaps)
    active_missing = sum(len(gap.missing_timestamps) for gap in active_gaps)
    active_gap_policy = classify_xauusd_gaps(active_gaps)
    active_share = (
        "0"
        if total_missing == 0
        else format_decimal(Decimal(active_missing) / Decimal(total_missing))
    )
    return "\n".join(
        [
            "Aurus real-data gap audit",
            f"total gaps: {len(gaps)}",
            f"total missing bars: {total_missing}",
            f"active strategy gaps: {len(active_gaps)}",
            f"active strategy missing bars: {active_missing}",
            f"active missing share: {active_share}",
            f"active expected closure gaps: {active_gap_policy.expected_closure_gaps}",
            f"active unexpected gaps: {active_gap_policy.unexpected_gaps}",
            f"active unexpected missing bars: {active_gap_policy.unexpected_missing_bars}",
            f"saved gap audit: {output}",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Audit real XAU/USD CSV missing bars.")
    parser.add_argument("--data", required=True, type=Path, help="MT5 XAU/USD 5m CSV path.")
    parser.add_argument(
        "--output",
        default=Path("artifacts/real-data-gap-audit.csv"),
        type=Path,
        help="CSV artifact path for gap audit rows.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_real_xauusd_5m_csv(args.data)
    strategy_config = current_best_real_config()
    active_gaps = active_strategy_gaps(data.report.missing_gaps, strategy_config)
    write_gap_audit_csv(
        path=args.output,
        gaps=data.report.missing_gaps,
        active_gaps=active_gaps,
    )
    print(
        format_gap_audit_summary(
            gaps=data.report.missing_gaps,
            active_gaps=active_gaps,
            output=args.output,
        )
    )


def _gap_id(gap: MissingBarGap) -> tuple[str, str]:
    return (gap.previous_timestamp.isoformat(), gap.next_timestamp.isoformat())


if __name__ == "__main__":
    main()
