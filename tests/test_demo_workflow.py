"""Tests for the demo workflow orchestrator."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurus.backtest.validation import (
    RealDataValidationReport,
    SpreadCostReport,
    ValidationMetrics,
)
from aurus.data.gap_policy import GapPolicyReport
from aurus.execution.run_paper_forward import PaperForwardResult
from aurus.ops.run_demo_workflow import (
    DemoWorkflowPaths,
    DemoWorkflowResult,
    format_demo_workflow_result,
    workflow_manifest,
    write_manifest,
)

NOW = datetime(2026, 4, 21, 14, 20, tzinfo=UTC)


def metrics(label: str) -> ValidationMetrics:
    return ValidationMetrics(
        label=label,
        start=NOW,
        end=NOW,
        bars=10,
        trades=2,
        win_rate=Decimal("0.5"),
        profit_factor=Decimal("1.2"),
        max_drawdown=Decimal("5"),
        net_pnl=Decimal("10"),
    )


def workflow_result(tmp_path: Path) -> DemoWorkflowResult:
    return DemoWorkflowResult(
        validation=RealDataValidationReport(
            full_sample=metrics("full"),
            segments=(metrics("early"),),
            walk_forward=(metrics("wf-001"),),
            spread_costs=SpreadCostReport(
                bars_with_spread=100,
                min_spread=Decimal("0.10"),
                median_spread=Decimal("0.20"),
                p95_spread=Decimal("0.30"),
                max_spread=Decimal("0.40"),
                bars_above_strategy_max_spread=0,
                strategy_max_spread=Decimal("0.50"),
                configured_entry_slippage=Decimal("0"),
                configured_exit_slippage=Decimal("0"),
            ),
            gap_policy=GapPolicyReport(
                expected_closure_gaps=0,
                unexpected_gaps=0,
                expected_missing_bars=0,
                unexpected_missing_bars=0,
            ),
            active_gap_policy=GapPolicyReport(
                expected_closure_gaps=0,
                unexpected_gaps=0,
                expected_missing_bars=0,
                unexpected_missing_bars=0,
            ),
        ),
        paper_forward=PaperForwardResult(
            latest_bar_timestamp=NOW.isoformat(),
            signal_count=0,
            submitted_orders=(),
            rejected_decisions=(),
        ),
        paths=DemoWorkflowPaths(
            validation_csv=tmp_path / "validation.csv",
            gap_audit_csv=tmp_path / "gaps.csv",
            manifest_json=tmp_path / "manifest.json",
            paper_state_dir=tmp_path / "paper",
        ),
    )


def test_workflow_manifest_summarizes_readiness(tmp_path: Path) -> None:
    manifest = workflow_manifest(workflow_result(tmp_path))

    assert manifest["ready"] is True
    assert manifest["blockers"] == []
    assert manifest["full_sample"]["trades"] == 2
    assert manifest["paper_forward"]["signals"] == 0


def test_write_manifest_persists_json(tmp_path: Path) -> None:
    result = workflow_result(tmp_path)

    write_manifest(result)

    contents = result.paths.manifest_json.read_text(encoding="utf-8")
    assert '"ready": true' in contents
    assert '"validation_csv"' in contents


def test_format_demo_workflow_result_includes_manifest_path(tmp_path: Path) -> None:
    result = workflow_result(tmp_path)

    summary = format_demo_workflow_result(result)

    assert "ready: True" in summary
    assert f"manifest: {result.paths.manifest_json}" in summary
