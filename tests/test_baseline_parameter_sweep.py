"""Tests for deterministic baseline parameter sweeps."""

from decimal import Decimal
from pathlib import Path

from aurus.backtest.sweep_baseline import (
    BaselineSweepGrid,
    BaselineSweepResult,
    format_ranked_table,
    rank_sweep_results,
    run_parameter_sweep,
    write_sweep_results,
)


def test_rank_sweep_results_uses_profit_factor_then_net_pnl() -> None:
    lower_pnl = sweep_result(profit_factor=Decimal("2"), net_pnl=Decimal("10"))
    higher_pnl = sweep_result(profit_factor=Decimal("2"), net_pnl=Decimal("20"))
    higher_profit_factor = sweep_result(profit_factor=Decimal("3"), net_pnl=Decimal("1"))

    ranked = rank_sweep_results([lower_pnl, higher_profit_factor, higher_pnl])

    assert ranked == [higher_profit_factor, higher_pnl, lower_pnl]


def test_write_sweep_results_persists_ranked_csv(tmp_path: Path) -> None:
    output_path = tmp_path / "sweep.csv"
    results = [
        sweep_result(profit_factor=Decimal("3"), net_pnl=Decimal("20")),
        sweep_result(profit_factor=None, net_pnl=Decimal("0"), total_trades=0),
    ]

    write_sweep_results(output_path, results)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("rank,confirmation_mode,min_atr")
    assert lines[1].startswith("1,relaxed,0.50")
    assert lines[2].endswith(",n/a,0,0")


def test_run_parameter_sweep_is_deterministic_on_sample_data(tmp_path: Path) -> None:
    data_path = Path("examples/baseline_sample_bars.csv")
    grid = BaselineSweepGrid(
        confirmation_modes=("strict", "relaxed"),
        min_atrs=(Decimal("0.50"),),
        max_spreads=(Decimal("0.50"),),
        context_ema_periods=(3,),
        execution_ema_periods=(3,),
    )

    first = run_parameter_sweep(data_path=data_path, grid=grid)
    second = run_parameter_sweep(data_path=data_path, grid=grid)

    assert first == second
    assert len(first) == 2
    assert "Top" not in format_ranked_table(first, limit=2)


def sweep_result(
    *,
    profit_factor: Decimal | None,
    net_pnl: Decimal,
    total_trades: int = 1,
) -> BaselineSweepResult:
    return BaselineSweepResult(
        confirmation_mode="relaxed",
        min_atr=Decimal("0.50"),
        max_spread=Decimal("0.50"),
        context_ema_period=3,
        execution_ema_period=3,
        total_trades=total_trades,
        win_rate=Decimal("1"),
        profit_factor=profit_factor,
        max_drawdown=Decimal("0"),
        net_pnl=net_pnl,
    )
