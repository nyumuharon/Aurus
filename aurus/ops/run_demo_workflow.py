"""Run the full MT5 demo validation and paper-forward workflow."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from aurus.backtest.audit_real_gaps import write_gap_audit_csv
from aurus.backtest.run_real_baseline import (
    current_best_real_backtest_config,
    current_best_real_config,
)
from aurus.backtest.validate_real_baseline import write_validation_csv
from aurus.backtest.validation import (
    RealDataValidationReport,
    active_strategy_gaps,
    evaluate_demo_readiness,
    run_real_data_validation,
)
from aurus.data import load_real_xauusd_5m_csv
from aurus.execution.run_paper_forward import (
    PaperForwardResult,
    run_paper_forward_once,
)


@dataclass(frozen=True)
class DemoWorkflowPaths:
    """Artifact paths produced by a demo workflow run."""

    validation_csv: Path
    gap_audit_csv: Path
    manifest_json: Path
    paper_state_dir: Path


@dataclass(frozen=True)
class DemoWorkflowResult:
    """Result of a complete demo workflow run."""

    validation: RealDataValidationReport
    paper_forward: PaperForwardResult
    paths: DemoWorkflowPaths


def run_demo_workflow(
    *,
    data_path: Path,
    artifact_dir: Path,
    paper_state_dir: Path,
    walk_forward_days: int = 30,
) -> DemoWorkflowResult:
    """Run validation, gap audit, paper-forward, and manifest generation."""

    strategy_config = current_best_real_config()
    backtest_config = current_best_real_backtest_config()
    data = load_real_xauusd_5m_csv(data_path)
    validation = run_real_data_validation(
        data=data,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        walk_forward_days=walk_forward_days,
    )
    paths = DemoWorkflowPaths(
        validation_csv=artifact_dir / "real-baseline-validation.csv",
        gap_audit_csv=artifact_dir / "real-data-gap-audit.csv",
        manifest_json=artifact_dir / "demo-workflow-manifest.json",
        paper_state_dir=paper_state_dir,
    )
    write_validation_csv(paths.validation_csv, validation)
    write_gap_audit_csv(
        path=paths.gap_audit_csv,
        gaps=data.report.missing_gaps,
        active_gaps=active_strategy_gaps(data.report.missing_gaps, strategy_config),
    )
    paper_forward = run_paper_forward_once(
        data=data,
        state_dir=paper_state_dir,
        strategy_config=strategy_config,
    )
    result = DemoWorkflowResult(
        validation=validation,
        paper_forward=paper_forward,
        paths=paths,
    )
    write_manifest(result)
    return result


def write_manifest(result: DemoWorkflowResult) -> None:
    """Persist a deterministic JSON manifest for the workflow run."""

    result.paths.manifest_json.parent.mkdir(parents=True, exist_ok=True)
    result.paths.manifest_json.write_text(
        json.dumps(workflow_manifest(result), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def workflow_manifest(result: DemoWorkflowResult) -> dict[str, Any]:
    """Build a JSON-serializable workflow manifest."""

    readiness = evaluate_demo_readiness(result.validation)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "ready": readiness.ready,
        "blockers": list(readiness.blockers),
        "warnings": list(readiness.warnings),
        "full_sample": {
            "trades": result.validation.full_sample.trades,
            "win_rate": str(result.validation.full_sample.win_rate),
            "profit_factor": (
                None
                if result.validation.full_sample.profit_factor is None
                else str(result.validation.full_sample.profit_factor)
            ),
            "max_drawdown": str(result.validation.full_sample.max_drawdown),
            "net_pnl": str(result.validation.full_sample.net_pnl),
        },
        "walk_forward": {
            "windows": len(result.validation.walk_forward),
            "profitable_windows": sum(
                1 for row in result.validation.walk_forward if row.net_pnl > Decimal("0")
            ),
            "positive_profit_factor_windows": sum(
                1
                for row in result.validation.walk_forward
                if row.profit_factor is not None and row.profit_factor > Decimal("1")
            ),
        },
        "gap_policy": {
            "active_unexpected_gaps": result.validation.active_gap_policy.unexpected_gaps,
            "active_unexpected_missing_bars": (
                result.validation.active_gap_policy.unexpected_missing_bars
            ),
        },
        "paper_forward": {
            "latest_bar_timestamp": result.paper_forward.latest_bar_timestamp,
            "signals": result.paper_forward.signal_count,
            "submitted_orders": len(result.paper_forward.submitted_orders),
            "rejected_decisions": len(result.paper_forward.rejected_decisions),
        },
        "artifacts": {
            "validation_csv": str(result.paths.validation_csv),
            "gap_audit_csv": str(result.paths.gap_audit_csv),
            "paper_state_dir": str(result.paths.paper_state_dir),
        },
    }


def format_demo_workflow_result(result: DemoWorkflowResult) -> str:
    """Render a concise workflow summary."""

    readiness = evaluate_demo_readiness(result.validation)
    return "\n".join(
        [
            "Aurus demo workflow",
            f"ready: {readiness.ready}",
            f"blockers: {_format_items(readiness.blockers)}",
            f"warnings: {_format_items(readiness.warnings)}",
            f"full trades: {result.validation.full_sample.trades}",
            f"full PF: {result.validation.full_sample.profit_factor}",
            f"full net PnL: {result.validation.full_sample.net_pnl}",
            f"paper signals: {result.paper_forward.signal_count}",
            f"paper submitted orders: {len(result.paper_forward.submitted_orders)}",
            f"manifest: {result.paths.manifest_json}",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run Aurus MT5 demo validation workflow.")
    parser.add_argument("--data", required=True, type=Path, help="MT5 XAU/USD 5m CSV path.")
    parser.add_argument(
        "--artifact-dir",
        default=Path("artifacts/demo-workflow"),
        type=Path,
        help="Directory for validation and manifest artifacts.",
    )
    parser.add_argument(
        "--paper-state-dir",
        default=Path("artifacts/demo-paper-forward"),
        type=Path,
        help="Directory for append-only paper execution state.",
    )
    parser.add_argument(
        "--walk-forward-days",
        default=30,
        type=int,
        help="Non-overlapping walk-forward window size.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    result = run_demo_workflow(
        data_path=args.data,
        artifact_dir=args.artifact_dir,
        paper_state_dir=args.paper_state_dir,
        walk_forward_days=args.walk_forward_days,
    )
    print(format_demo_workflow_result(result))


def _format_items(items: tuple[str, ...]) -> str:
    return "none" if not items else " | ".join(items)


if __name__ == "__main__":
    main()
