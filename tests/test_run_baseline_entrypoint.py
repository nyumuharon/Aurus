"""Tests for the runnable baseline backtest entry point."""

from pathlib import Path

from aurus.backtest.run_baseline import config_from_args, run_baseline_backtest
from aurus.ops import CsvTradeLedgerRepository, EventJournal

SAMPLE_DATA = Path("examples/baseline_sample_bars.csv")


def args(tmp_path, **overrides: object):
    values = {
        "data": SAMPLE_DATA,
        "ledger": tmp_path / "ledger.csv",
        "events": tmp_path / "events.jsonl",
        "initial_cash": "100000",
        "quantity": "1",
        "spread": "0",
        "slippage": "0",
        "context_ema_period": 3,
        "execution_ema_period": 3,
        "atr_period": 3,
        "min_atr": "0.50",
        "max_spread": "0.50",
        "atr_stop_floor_multiplier": "1",
        "reward_risk": "2",
    }
    values.update(overrides)
    return type("Args", (), values)()


def test_run_baseline_backtest_writes_artifacts(tmp_path) -> None:
    config = config_from_args(args(tmp_path))

    result = run_baseline_backtest(config)

    assert config.trade_ledger_path.exists()
    assert config.event_log_path.exists()
    assert len(result.event_log) > 0
    assert len(result.trades) == 1
    assert len(EventJournal(config.event_log_path).read()) == len(result.events)
    assert CsvTradeLedgerRepository(config.trade_ledger_path).read_all() == result.trades


def test_config_from_args_builds_typed_config(tmp_path) -> None:
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
        )
    )

    assert config.data_path == SAMPLE_DATA
    assert str(config.backtest.initial_cash) == "50000"
    assert str(config.strategy.quantity) == "2"
    assert str(config.strategy.min_atr) == "0.75"
    assert config.strategy.context_ema_period == 10

