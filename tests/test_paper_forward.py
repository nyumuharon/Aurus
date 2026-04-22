"""Tests for the paper-forward decision runner."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurus.common.schemas import BarEvent, RiskAction, RiskDecision, Side, SignalEvent
from aurus.data.real_csv import IngestedMarketData, RealCsvIngestionReport
from aurus.execution import InMemoryExecutionRepository, PaperExecutionAdapter
from aurus.execution.run_paper_forward import (
    build_risk_snapshot,
    client_order_key,
    default_forward_risk_config,
    order_intent_from_signal,
    run_paper_forward_once,
)
from aurus.strategy import BaselineStrategyConfig

NOW = datetime(2026, 4, 21, 10, 0, tzinfo=UTC)


def bar(index: int, *, spread: Decimal = Decimal("0.20")) -> BarEvent:
    timestamp = NOW + timedelta(minutes=5 * index)
    return BarEvent(
        timestamp=timestamp,
        correlation_id=f"bar-{index}",
        instrument="XAU/USD",
        timeframe="5m",
        open=Decimal("2400"),
        high=Decimal("2401"),
        low=Decimal("2399"),
        close=Decimal("2400"),
        volume=Decimal("1"),
        spread=spread,
    )


def signal() -> SignalEvent:
    return SignalEvent(
        timestamp=NOW,
        correlation_id="signal-corr",
        signal_id="signal-1",
        strategy_id="test",
        instrument="XAU/USD",
        side=Side.BUY,
        strength=Decimal("1"),
        features={"quantity": "2", "stop_loss": "2390"},
    )


def decision() -> RiskDecision:
    return RiskDecision(
        timestamp=NOW,
        correlation_id="signal-corr",
        decision_id="risk-signal-1",
        signal_id="signal-1",
        approved=True,
        action=RiskAction.APPROVE,
        reason="allowed",
    )


def data_with_no_signal(tmp_path: Path) -> IngestedMarketData:
    execution_bars = [bar(0), bar(1)]
    return IngestedMarketData(
        execution_bars=execution_bars,
        context_bars=[],
        report=RealCsvIngestionReport(
            source_path=tmp_path / "sample.csv",
            input_rows=len(execution_bars),
            output_bars=len(execution_bars),
            duplicates_removed=0,
            missing_gaps=(),
        ),
    )


def test_paper_forward_records_no_signal_alert(tmp_path: Path) -> None:
    result = run_paper_forward_once(data=data_with_no_signal(tmp_path), state_dir=tmp_path)

    assert result.signal_count == 0
    assert result.submitted_orders == ()
    assert result.alert is not None
    assert (tmp_path / "journal" / "paper-forward.jsonl").exists()


def test_order_intent_uses_signal_quantity_and_risk_decision() -> None:
    intent = order_intent_from_signal(signal=signal(), decision=decision())

    assert intent.quantity == Decimal("2")
    assert intent.risk_decision_id == "risk-signal-1"
    assert intent.side == Side.BUY


def test_risk_snapshot_uses_paper_state_for_duplicates_and_positions() -> None:
    adapter = PaperExecutionAdapter(repository=InMemoryExecutionRepository(), clock=lambda: NOW)
    intent = order_intent_from_signal(signal=signal(), decision=decision())
    adapter.submit_order(intent, client_order_key=client_order_key(signal()))

    snapshot = build_risk_snapshot(signal(), bar(0), adapter)

    assert snapshot.open_positions == 1
    assert snapshot.trades_today == 1
    assert snapshot.seen_signal_ids == frozenset({"signal-1"})
    assert snapshot.spread == Decimal("0.20")


def test_default_forward_risk_config_uses_strategy_spread_limit() -> None:
    risk_config = default_forward_risk_config(
        BaselineStrategyConfig(max_spread=Decimal("0.33"))
    )

    assert risk_config.max_spread == Decimal("0.33")
    assert risk_config.max_concurrent_positions == 1
