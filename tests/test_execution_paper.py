"""Tests for paper execution adapter behavior."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from aurus.common.schemas import OrderIntent, OrderStatus, OrderType, Side
from aurus.execution import InMemoryExecutionRepository, PaperExecutionAdapter, PaperExecutionConfig

NOW = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)


def clock() -> datetime:
    return NOW


def intent(
    *,
    side: Side = Side.BUY,
    quantity: Decimal = Decimal("1"),
    order_type: OrderType = OrderType.MARKET,
    limit_price: Decimal | None = None,
) -> OrderIntent:
    return OrderIntent(
        timestamp=NOW,
        correlation_id="corr-1",
        intent_id="intent-1",
        risk_decision_id="risk-1",
        instrument="XAU/USD",
        side=side,
        order_type=order_type,
        quantity=quantity,
        limit_price=limit_price,
    )


def test_idempotent_submissions_return_existing_order_and_single_fill() -> None:
    adapter = PaperExecutionAdapter(clock=clock)

    first = adapter.submit_order(intent(), client_order_key="key-1")
    second = adapter.submit_order(intent(quantity=Decimal("2")), client_order_key="key-1")

    assert second == first
    assert len(adapter.list_fills()) == 1
    assert adapter.positions()[0].quantity == Decimal("1")


def test_position_state_transitions_open_add_reduce_and_close(caplog) -> None:
    adapter = PaperExecutionAdapter(
        clock=clock,
        config=PaperExecutionConfig(default_fill_price=Decimal("100")),
    )

    adapter.submit_order(intent(side=Side.BUY, quantity=Decimal("1")), client_order_key="buy-1")
    adapter.submit_order(intent(side=Side.BUY, quantity=Decimal("2")), client_order_key="buy-2")
    adapter.submit_order(intent(side=Side.SELL, quantity=Decimal("1")), client_order_key="sell-1")

    position = adapter.positions()[0]
    assert position.quantity == Decimal("2")
    assert position.average_price == Decimal("100")

    with caplog.at_level("INFO", logger="aurus.execution.paper"):
        adapter.submit_order(
            intent(side=Side.SELL, quantity=Decimal("2")),
            client_order_key="sell-2",
        )

    closed = adapter.positions()[0]
    assert closed.quantity == Decimal("0")
    assert closed.average_price is None
    assert any(record.event == "execution.position_closed" for record in caplog.records)


def test_rejection_handling_persists_order_without_fill_and_logs(caplog) -> None:
    adapter = PaperExecutionAdapter(
        clock=clock,
        config=PaperExecutionConfig(max_quantity=Decimal("1")),
    )

    with caplog.at_level("WARNING", logger="aurus.execution.paper"):
        order = adapter.submit_order(intent(quantity=Decimal("2")), client_order_key="too-large")

    assert order.status == OrderStatus.REJECTED
    assert order.message == "quantity exceeds paper execution limit"
    assert adapter.list_fills() == ()
    assert adapter.positions() == ()
    assert any(record.event == "execution.order_rejected" for record in caplog.records)


def test_order_normalization_rounds_quantity_and_price() -> None:
    adapter = PaperExecutionAdapter(
        clock=clock,
        config=PaperExecutionConfig(
            price_increment=Decimal("0.05"),
            quantity_increment=Decimal("0.10"),
        ),
    )

    order = adapter.submit_order(
        intent(
            quantity=Decimal("1.04"),
            order_type=OrderType.LIMIT,
            limit_price=Decimal("2380.03"),
        ),
        client_order_key="normalized",
    )

    assert order.quantity == Decimal("1.00")
    assert order.average_fill_price == Decimal("2380.05")


def test_reconciliation_hooks_restore_orders_fills_and_positions() -> None:
    repository = InMemoryExecutionRepository()
    first = PaperExecutionAdapter(repository=repository, clock=clock)
    first.submit_order(intent(quantity=Decimal("1")), client_order_key="key-1")

    restarted = PaperExecutionAdapter(repository=repository, clock=clock)

    assert restarted.get_order("key-1") == first.get_order("key-1")
    assert restarted.list_fills() == first.list_fills()
    assert restarted.positions() == first.positions()


def test_reconcile_refreshes_existing_adapter_from_repository() -> None:
    repository = InMemoryExecutionRepository()
    first = PaperExecutionAdapter(repository=repository, clock=clock)
    second = PaperExecutionAdapter(repository=repository, clock=clock)

    first.submit_order(intent(quantity=Decimal("1")), client_order_key="key-1")
    assert second.get_order("key-1") is None

    second.reconcile()

    assert second.get_order("key-1") == first.get_order("key-1")
    assert second.positions() == first.positions()


def test_naive_execution_clock_is_rejected() -> None:
    def naive_clock() -> datetime:
        return datetime(2026, 4, 21, 12, 0)

    adapter = PaperExecutionAdapter(clock=naive_clock)

    with pytest.raises(ValueError, match="timezone-aware"):
        adapter.submit_order(intent(), client_order_key="key-1")
