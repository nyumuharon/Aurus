"""Tests for operational logging, journals, ledgers, and metrics."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurus.backtest.types import BacktestResult, EquityPoint, TradeRecord
from aurus.common.schemas import BarEvent
from aurus.ops import (
    CsvTradeLedgerRepository,
    EventJournal,
    InMemoryTradeLedgerRepository,
    calculate_metrics,
    summarize_metrics,
)


def bar_event(index: int) -> BarEvent:
    price = Decimal("2380") + Decimal(index)
    return BarEvent(
        timestamp=datetime(2026, 4, 21, 8, 0, tzinfo=UTC) + timedelta(minutes=index),
        correlation_id=f"bar-{index}",
        instrument="XAU/USD",
        timeframe="1m",
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("1"),
    )


def trade(index: int, net_pnl: Decimal) -> TradeRecord:
    entry_timestamp = datetime(2026, 4, 21, 8, 0, tzinfo=UTC) + timedelta(minutes=index)
    return TradeRecord(
        trade_id=f"trade-{index}",
        instrument="XAU/USD",
        side="buy",
        quantity=Decimal("1"),
        entry_timestamp=entry_timestamp,
        exit_timestamp=entry_timestamp + timedelta(minutes=1),
        entry_price=Decimal("100"),
        exit_price=Decimal("100") + net_pnl,
        gross_pnl=net_pnl,
        commission=Decimal("0"),
        net_pnl=net_pnl,
        exit_reason="test",
    )


def equity_curve() -> tuple[EquityPoint, ...]:
    base_time = datetime(2026, 4, 21, 8, 0, tzinfo=UTC)
    return (
        EquityPoint(base_time, Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("1000")),
        EquityPoint(
            base_time + timedelta(minutes=1),
            Decimal("990"),
            Decimal("-10"),
            Decimal("0"),
            Decimal("990"),
        ),
        EquityPoint(
            base_time + timedelta(minutes=2),
            Decimal("1010"),
            Decimal("10"),
            Decimal("0"),
            Decimal("1010"),
        ),
        EquityPoint(
            base_time + timedelta(minutes=3),
            Decimal("980"),
            Decimal("-20"),
            Decimal("0"),
            Decimal("980"),
        ),
    )


def test_journal_write_read_round_trip(tmp_path: Path) -> None:
    journal = EventJournal(tmp_path / "events.jsonl")
    events = (bar_event(0), bar_event(1))

    journal.append_many(events)

    assert journal.read() == events


def test_metrics_calculations() -> None:
    trades = (trade(0, Decimal("10")), trade(1, Decimal("-5")), trade(2, Decimal("15")))

    metrics = calculate_metrics(trades, equity_curve())

    assert metrics.total_pnl == Decimal("20")
    assert metrics.max_drawdown == Decimal("30")
    assert metrics.win_rate == Decimal("2") / Decimal("3")
    assert metrics.profit_factor == Decimal("5")
    assert metrics.trade_count == 3
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1


def test_metrics_handle_no_losing_trades_profit_factor() -> None:
    metrics = calculate_metrics((trade(0, Decimal("10")),), ())

    assert metrics.max_drawdown == Decimal("0")
    assert metrics.profit_factor is None


def test_in_memory_ledger_persistence_behavior() -> None:
    repository = InMemoryTradeLedgerRepository()
    trades = (trade(0, Decimal("10")), trade(1, Decimal("-5")))

    repository.append(trades[0])
    repository.append_many((trades[1],))

    assert repository.read_all() == trades


def test_csv_ledger_persistence_behavior(tmp_path: Path) -> None:
    repository = CsvTradeLedgerRepository(tmp_path / "ledger.csv")
    trades = (trade(0, Decimal("10")), trade(1, Decimal("-5")))

    repository.append_many(trades)

    assert repository.read_all() == trades


def test_run_summary_output_contains_key_metrics() -> None:
    metrics = calculate_metrics((trade(0, Decimal("10")), trade(1, Decimal("-5"))), equity_curve())
    summary = summarize_metrics(metrics)

    assert "Aurus run summary" in summary
    assert "trades: 2" in summary
    assert "total_pnl: 5" in summary
    assert "max_drawdown: 30" in summary


def test_backtest_result_summary_smoke() -> None:
    result = BacktestResult(
        trades=(trade(0, Decimal("10")),),
        equity_curve=equity_curve(),
        event_log=(),
        events=(),
    )

    assert result.trades[0].net_pnl == Decimal("10")
