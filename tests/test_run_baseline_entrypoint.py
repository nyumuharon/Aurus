"""Tests for the runnable baseline backtest entry point."""

import argparse
from datetime import UTC, timedelta
from itertools import pairwise
from pathlib import Path

from aurus.backtest.run_baseline import (
    DEFAULT_LARGE_SAMPLE_DATA_PATH,
    DEFAULT_SAMPLE_DATA_PATH,
    LARGE_SAMPLE_5M_BAR_COUNT,
    config_from_args,
    ensure_large_sample_dataset,
    ensure_sample_dataset,
    format_baseline_summary,
    run_baseline_backtest,
)
from aurus.data import CsvBarLoader
from aurus.ops import CsvTradeLedgerRepository, EventJournal

SAMPLE_DATA = DEFAULT_SAMPLE_DATA_PATH


def args(
    tmp_path: Path,
    *,
    initial_cash: str = "100000",
    quantity: str = "1",
    spread: str = "0",
    slippage: str = "0",
    context_ema_period: int = 3,
    execution_ema_period: int = 3,
    atr_period: int = 3,
    min_atr: str = "0.50",
    max_spread: str = "0.50",
    atr_stop_floor_multiplier: str = "1",
    reward_risk: str = "2",
    data: Path | None = SAMPLE_DATA,
    large_sample: bool = False,
    diagnostics: bool = False,
    diagnostics_file: Path | None = None,
    confirmation_mode: str = "strict",
) -> argparse.Namespace:
    return argparse.Namespace(
        data=data,
        large_sample=large_sample,
        diagnostics=diagnostics,
        diagnostics_file=diagnostics_file,
        ledger=tmp_path / "ledger.csv",
        events=tmp_path / "events.jsonl",
        initial_cash=initial_cash,
        quantity=quantity,
        spread=spread,
        slippage=slippage,
        context_ema_period=context_ema_period,
        execution_ema_period=execution_ema_period,
        atr_period=atr_period,
        min_atr=min_atr,
        max_spread=max_spread,
        atr_stop_floor_multiplier=atr_stop_floor_multiplier,
        reward_risk=reward_risk,
        confirmation_mode=confirmation_mode,
    )


def test_run_baseline_backtest_writes_artifacts(tmp_path: Path) -> None:
    config = config_from_args(args(tmp_path))

    result = run_baseline_backtest(config)

    assert config.trade_ledger_path.exists()
    assert config.event_log_path.exists()
    assert len(result.event_log) > 0
    assert len(result.trades) == 1
    assert len(EventJournal(config.event_log_path).read()) == len(result.events)
    assert CsvTradeLedgerRepository(config.trade_ledger_path).read_all() == result.trades


def test_run_baseline_backtest_overwrites_artifacts_deterministically(tmp_path: Path) -> None:
    config = config_from_args(args(tmp_path))

    first = run_baseline_backtest(config)
    first_ledger = config.trade_ledger_path.read_text(encoding="utf-8")
    first_events = config.event_log_path.read_text(encoding="utf-8")
    second = run_baseline_backtest(config)

    assert second.event_log == first.event_log
    assert config.trade_ledger_path.read_text(encoding="utf-8") == first_ledger
    assert config.event_log_path.read_text(encoding="utf-8") == first_events


def test_sample_dataset_is_created_when_missing(tmp_path: Path) -> None:
    sample_path = tmp_path / "examples" / "baseline_sample_bars.csv"

    created_path = ensure_sample_dataset(sample_path)

    assert created_path == sample_path
    assert sample_path.exists()
    assert "timestamp,instrument,timeframe" in sample_path.read_text(encoding="utf-8")


def test_large_sample_dataset_is_created_with_continuous_utc_bars(tmp_path: Path) -> None:
    sample_path = tmp_path / "examples" / "baseline_large_sample.csv"

    created_path = ensure_large_sample_dataset(sample_path)
    bars = CsvBarLoader(created_path).load_bars(instrument="XAU/USD", timeframe="5m")
    spreads = {bar.spread for bar in bars}

    assert created_path == sample_path
    assert len(bars) == LARGE_SAMPLE_5M_BAR_COUNT
    assert bars[0].timestamp.tzinfo == UTC
    assert all(
        next_bar.timestamp - previous_bar.timestamp == timedelta(minutes=5)
        for previous_bar, next_bar in pairwise(bars)
    )
    assert len(spreads) > 10
    assert min(bar.close for bar in bars) < bars[0].close
    assert max(bar.close for bar in bars) > bars[0].close


def test_config_from_args_builds_typed_config(tmp_path: Path) -> None:
    config = config_from_args(
        args(
            tmp_path,
            initial_cash="50000",
            quantity="2",
            spread="0.10",
            slippage="0.05",
            min_atr="0.75",
            max_spread="0.30",
            context_ema_period=10,
            confirmation_mode="relaxed",
        )
    )

    assert config.data_path == SAMPLE_DATA
    assert str(config.backtest.initial_cash) == "50000"
    assert str(config.strategy.quantity) == "2"
    assert str(config.strategy.min_atr) == "0.75"
    assert config.strategy.context_ema_period == 10
    assert config.strategy.confirmation_mode == "relaxed"


def test_config_from_args_can_select_large_sample(tmp_path: Path) -> None:
    config = config_from_args(args(tmp_path, data=None, large_sample=True))

    assert config.data_path == DEFAULT_LARGE_SAMPLE_DATA_PATH


def test_config_from_args_prefers_explicit_data_over_large_sample(tmp_path: Path) -> None:
    explicit_data = tmp_path / "custom.csv"

    config = config_from_args(args(tmp_path, data=explicit_data, large_sample=True))

    assert config.data_path == explicit_data


def test_run_baseline_backtest_writes_diagnostics_when_enabled(tmp_path: Path) -> None:
    diagnostics_file = tmp_path / "diagnostics.txt"
    config = config_from_args(args(tmp_path, diagnostics=True, diagnostics_file=diagnostics_file))

    result = run_baseline_backtest(config)

    assert len(result.trades) == 1
    assert config.diagnostics is not None
    assert config.diagnostics.final_signal_emission == 2
    assert diagnostics_file.exists()
    assert "Baseline diagnostic rejection funnel" in diagnostics_file.read_text(encoding="utf-8")


def test_baseline_summary_uses_required_fields(tmp_path: Path) -> None:
    result = run_baseline_backtest(config_from_args(args(tmp_path)))

    summary = format_baseline_summary(result)

    assert "total trades: 1" in summary
    assert "win rate:" in summary
    assert "profit factor:" in summary
    assert "max drawdown:" in summary
    assert "net PnL:" in summary
