"""Tests for baseline execution-friction stress runs."""

from decimal import Decimal
from pathlib import Path

from aurus.backtest.stress_baseline import (
    StressResult,
    StressScenario,
    format_stress_table,
    performance_collapses,
    run_stress_test,
    write_stress_results,
)


def test_run_stress_test_is_deterministic_on_sample_data() -> None:
    data_path = Path("examples/baseline_sample_bars.csv")
    scenarios = (
        StressScenario(
            name="normal",
            entry_slippage=Decimal("0"),
            exit_slippage=Decimal("0"),
            spread_multiplier=Decimal("1"),
        ),
        StressScenario(
            name="severe stress",
            entry_slippage=Decimal("0.10"),
            exit_slippage=Decimal("0.10"),
            spread_multiplier=Decimal("2"),
        ),
    )

    first = run_stress_test(data_path=data_path, scenarios=scenarios)
    second = run_stress_test(data_path=data_path, scenarios=scenarios)

    assert first == second
    assert [result.scenario.name for result in first] == ["normal", "severe stress"]


def test_write_stress_results_persists_csv(tmp_path: Path) -> None:
    output_path = tmp_path / "stress.csv"
    result = stress_result(name="normal", net_pnl=Decimal("1"), profit_factor=None)

    write_stress_results(output_path, [result])

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("scenario,entry_slippage,exit_slippage")
    assert lines[1].startswith("normal,0,0,1")
    assert lines[1].endswith(",n/a,0,1")


def test_format_stress_table_and_collapse_check() -> None:
    normal = stress_result(name="normal", net_pnl=Decimal("10"), profit_factor=Decimal("2"))
    severe = stress_result(
        name="severe stress",
        net_pnl=Decimal("-1"),
        profit_factor=Decimal("0.5"),
    )

    table = format_stress_table([normal, severe])

    assert "scenario" in table
    assert "severe stress" in table
    assert performance_collapses([normal, severe])


def stress_result(
    *,
    name: str,
    net_pnl: Decimal,
    profit_factor: Decimal | None,
) -> StressResult:
    return StressResult(
        scenario=StressScenario(
            name=name,
            entry_slippage=Decimal("0"),
            exit_slippage=Decimal("0"),
            spread_multiplier=Decimal("1"),
        ),
        total_trades=1,
        win_rate=Decimal("1"),
        profit_factor=profit_factor,
        max_drawdown=Decimal("0"),
        net_pnl=net_pnl,
    )
