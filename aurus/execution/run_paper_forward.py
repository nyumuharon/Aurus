"""Run one auditable paper-forward decision cycle from the latest MT5 CSV bar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from aurus.backtest.run_real_baseline import current_best_real_config
from aurus.common.schemas import (
    AlertSeverity,
    BarEvent,
    OrderEvent,
    OrderIntent,
    OrderType,
    RiskDecision,
    SignalEvent,
    SourceMetadata,
    SystemAlert,
    TimeInForce,
)
from aurus.data import IngestedMarketData, load_real_xauusd_5m_csv
from aurus.data.sessions import tag_session
from aurus.execution import JsonlExecutionRepository, PaperExecutionAdapter, PaperExecutionConfig
from aurus.ops import EventJournal
from aurus.risk import RiskConfig, RiskKernel, RiskSnapshot
from aurus.strategy import BaselineStrategyConfig, BaselineXauUsdStrategy

FORWARD_SOURCE = SourceMetadata(name="aurus-paper-forward", kind="execution_workflow")


@dataclass(frozen=True)
class PaperForwardResult:
    """Outcome of one forward paper decision cycle."""

    latest_bar_timestamp: str
    signal_count: int
    submitted_orders: tuple[OrderEvent, ...]
    rejected_decisions: tuple[RiskDecision, ...]
    alert: SystemAlert | None = None


def run_paper_forward_once(
    *,
    data: IngestedMarketData,
    state_dir: Path,
    strategy_config: BaselineStrategyConfig | None = None,
    risk_config: RiskConfig | None = None,
) -> PaperForwardResult:
    """Evaluate the latest closed bar and submit approved signals to paper execution.

    The function intentionally does not backfill historical orders. It evaluates only the
    current point-in-time strategy output for the latest loaded bar, then relies on
    client-order idempotency to make repeated runs restart-safe.
    """

    if not data.execution_bars:
        raise ValueError("paper forward run requires at least one execution bar")

    latest_bar = data.execution_bars[-1]
    strategy_parameters = strategy_config or current_best_real_config()
    strategy = BaselineXauUsdStrategy(
        context_bars=data.context_bars,
        config=strategy_parameters,
    )
    signals = tuple(strategy(data.execution_bars))
    repository = JsonlExecutionRepository(state_dir / "execution")
    adapter = PaperExecutionAdapter(
        repository=repository,
        config=PaperExecutionConfig(
            account_id="mt5-demo-paper",
            default_fill_price=latest_bar.close,
        ),
        clock=lambda: latest_bar.timestamp,
    )
    journal = EventJournal(state_dir / "journal" / "paper-forward.jsonl")
    risk_kernel = RiskKernel(risk_config or default_forward_risk_config(strategy_parameters))

    if not signals:
        alert = SystemAlert(
            timestamp=latest_bar.timestamp,
            correlation_id=f"paper-forward-{latest_bar.correlation_id}",
            source=FORWARD_SOURCE,
            alert_id=f"paper-forward-no-signal-{latest_bar.timestamp.isoformat()}",
            severity=AlertSeverity.INFO,
            component="paper_forward",
            message="no baseline signal on latest closed bar",
            details={"latest_bar_timestamp": latest_bar.timestamp.isoformat()},
        )
        journal.append(alert)
        return PaperForwardResult(
            latest_bar_timestamp=latest_bar.timestamp.isoformat(),
            signal_count=0,
            submitted_orders=(),
            rejected_decisions=(),
            alert=alert,
        )

    submitted_orders: list[OrderEvent] = []
    rejected_decisions: list[RiskDecision] = []
    for signal in signals:
        journal.append(signal)
        decision = risk_kernel.evaluate(signal, build_risk_snapshot(signal, latest_bar, adapter))
        journal.append(decision)
        if not decision.approved:
            rejected_decisions.append(decision)
            continue

        intent = order_intent_from_signal(signal=signal, decision=decision)
        journal.append(intent)
        order = adapter.submit_order(intent, client_order_key=client_order_key(signal))
        journal.append(order)
        submitted_orders.append(order)
        journal.append_many(adapter.list_fills())
        journal.append_many(adapter.positions())

    return PaperForwardResult(
        latest_bar_timestamp=latest_bar.timestamp.isoformat(),
        signal_count=len(signals),
        submitted_orders=tuple(submitted_orders),
        rejected_decisions=tuple(rejected_decisions),
    )


def default_forward_risk_config(strategy_config: BaselineStrategyConfig) -> RiskConfig:
    """Conservative default risk guardrails for demo paper-forward decisions."""

    return RiskConfig(
        max_daily_realized_loss=Decimal("500"),
        max_total_drawdown=Decimal("1000"),
        max_trades_per_day=20,
        max_spread=strategy_config.max_spread,
        max_consecutive_losses=3,
        require_stop_loss=True,
        max_concurrent_positions=1,
    )


def build_risk_snapshot(
    signal: SignalEvent,
    latest_bar: BarEvent,
    adapter: PaperExecutionAdapter,
) -> RiskSnapshot:
    """Build a deterministic risk snapshot from broker-neutral paper state."""

    positions = adapter.positions()
    open_positions = sum(1 for position in positions if position.quantity != Decimal("0"))
    seen_signal_ids = frozenset(
        key.removeprefix("paper-forward:")
        for key, _order in adapter.repository.list_orders()
        if key.startswith("paper-forward:")
    )
    return RiskSnapshot(
        timestamp=signal.timestamp,
        realized_pnl_today=Decimal("0"),
        current_equity=Decimal("100000"),
        peak_equity=Decimal("100000"),
        trades_today=_orders_today(adapter, latest_bar),
        spread=latest_bar.spread or Decimal("0"),
        session=tag_session(latest_bar.timestamp).value,
        seen_signal_ids=seen_signal_ids,
        consecutive_losses=0,
        open_positions=open_positions,
    )


def order_intent_from_signal(
    *,
    signal: SignalEvent,
    decision: RiskDecision,
) -> OrderIntent:
    """Convert an approved strategy signal into a broker-neutral market intent."""

    quantity = Decimal(str(signal.features.get("quantity", "1")))
    return OrderIntent(
        timestamp=signal.timestamp,
        correlation_id=signal.correlation_id,
        source=FORWARD_SOURCE,
        intent_id=f"paper-forward-intent-{signal.signal_id}",
        risk_decision_id=decision.decision_id,
        instrument=signal.instrument,
        side=signal.side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        time_in_force=TimeInForce.IOC,
    )


def client_order_key(signal: SignalEvent) -> str:
    """Stable idempotency key for one signal."""

    return f"paper-forward:{signal.signal_id}"


def _orders_today(adapter: PaperExecutionAdapter, latest_bar: BarEvent) -> int:
    latest_date = latest_bar.timestamp.date()
    return sum(
        1
        for _key, order in adapter.repository.list_orders()
        if order.timestamp.date() == latest_date
    )


def format_paper_forward_result(result: PaperForwardResult) -> str:
    """Render a concise CLI summary."""

    return "\n".join(
        [
            "Aurus paper-forward run",
            f"latest bar: {result.latest_bar_timestamp}",
            f"signals: {result.signal_count}",
            f"submitted orders: {len(result.submitted_orders)}",
            f"rejected decisions: {len(result.rejected_decisions)}",
            f"alert: {result.alert.message if result.alert is not None else 'none'}",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run one MT5 CSV paper-forward cycle.")
    parser.add_argument("--data", required=True, type=Path, help="MT5 XAU/USD 5m CSV path.")
    parser.add_argument(
        "--state-dir",
        default=Path("artifacts/demo-paper-forward"),
        type=Path,
        help="Directory for append-only paper state and journal files.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    data = load_real_xauusd_5m_csv(args.data)
    result = run_paper_forward_once(data=data, state_dir=args.state_dir)
    print(format_paper_forward_result(result))
    print(f"state directory: {args.state_dir}")


if __name__ == "__main__":
    main()
