"""Paper execution adapter."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from aurus.common.schemas import (
    FillEvent,
    OrderEvent,
    OrderIntent,
    OrderStatus,
    OrderType,
    PositionSnapshot,
    Side,
    SourceMetadata,
)
from aurus.execution.interfaces import ExecutionRepository
from aurus.execution.repository import InMemoryExecutionRepository

LOGGER = logging.getLogger(__name__)
PAPER_SOURCE = SourceMetadata(name="paper-execution", kind="execution_adapter")


@dataclass(frozen=True)
class PaperExecutionConfig:
    """Explicit paper execution assumptions."""

    account_id: str = "paper"
    price_increment: Decimal = Decimal("0.01")
    quantity_increment: Decimal = Decimal("0.01")
    max_quantity: Decimal | None = None
    reject_non_market_orders: bool = False
    default_fill_price: Decimal = Decimal("1")
    commission_per_fill: Decimal = Decimal("0")


class PaperExecutionAdapter:
    """Deterministic broker-neutral paper execution adapter."""

    def __init__(
        self,
        *,
        repository: ExecutionRepository | None = None,
        config: PaperExecutionConfig | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or InMemoryExecutionRepository()
        self.config = config or PaperExecutionConfig()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._orders: dict[str, OrderEvent] = {}
        self._fills: list[FillEvent] = []
        self._positions: dict[str, PositionSnapshot] = {}
        self.reconcile()

    def submit_order(self, intent: OrderIntent, *, client_order_key: str) -> OrderEvent:
        existing = self._orders.get(client_order_key) or self.repository.get_order(client_order_key)
        if existing is not None:
            self._orders[client_order_key] = existing
            return existing

        normalized_intent = normalize_order_intent(intent, self.config)
        rejection_reason = self._rejection_reason(normalized_intent)
        if rejection_reason is not None:
            order = self._build_order(
                normalized_intent,
                client_order_key=client_order_key,
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                average_fill_price=None,
                message=rejection_reason,
            )
            self._save_order(client_order_key, order)
            LOGGER.warning(
                "paper order rejected",
                extra={
                    "event": "execution.order_rejected",
                    "client_order_key": client_order_key,
                    "order_id": order.order_id,
                    "reason": rejection_reason,
                },
            )
            return order

        fill_price = execution_price(normalized_intent, self.config)
        order = self._build_order(
            normalized_intent,
            client_order_key=client_order_key,
            status=OrderStatus.FILLED,
            filled_quantity=normalized_intent.quantity,
            average_fill_price=fill_price,
            message="paper fill",
        )
        fill = FillEvent(
            timestamp=order.timestamp,
            correlation_id=normalized_intent.correlation_id,
            source=PAPER_SOURCE,
            fill_id=f"fill-{client_order_key}",
            order_id=order.order_id,
            instrument=normalized_intent.instrument,
            side=normalized_intent.side,
            quantity=normalized_intent.quantity,
            price=fill_price,
            commission=self.config.commission_per_fill,
            liquidity="paper",
        )

        self._save_order(client_order_key, order)
        self.repository.save_fill(fill)
        self._fills.append(fill)
        self._apply_fill(fill)

        LOGGER.info(
            "paper order accepted",
            extra={
                "event": "execution.order_accepted",
                "client_order_key": client_order_key,
                "order_id": order.order_id,
            },
        )
        LOGGER.info(
            "paper order filled",
            extra={
                "event": "execution.order_filled",
                "client_order_key": client_order_key,
                "order_id": order.order_id,
                "fill_id": fill.fill_id,
                "price": str(fill.price),
                "quantity": str(fill.quantity),
            },
        )
        if self._positions[fill.instrument].quantity == Decimal("0"):
            LOGGER.info(
                "paper position closed",
                extra={
                    "event": "execution.position_closed",
                    "instrument": fill.instrument,
                    "order_id": order.order_id,
                },
            )
        return order

    def get_order(self, client_order_key: str) -> OrderEvent | None:
        return self._orders.get(client_order_key)

    def list_fills(self) -> tuple[FillEvent, ...]:
        return tuple(self._fills)

    def positions(self) -> tuple[PositionSnapshot, ...]:
        return tuple(sorted(self._positions.values(), key=lambda item: item.instrument))

    def reconcile(self) -> None:
        self._orders = dict(self.repository.list_orders())
        self._fills = list(self.repository.list_fills())
        self._positions = {
            position.instrument: position for position in self.repository.list_positions()
        }

    def _build_order(
        self,
        intent: OrderIntent,
        *,
        client_order_key: str,
        status: OrderStatus,
        filled_quantity: Decimal,
        average_fill_price: Decimal | None,
        message: str,
    ) -> OrderEvent:
        return OrderEvent(
            timestamp=self._timestamp(),
            correlation_id=intent.correlation_id,
            source=PAPER_SOURCE,
            order_id=f"paper-{client_order_key}",
            intent_id=intent.intent_id,
            broker_order_id=f"paper-{client_order_key}",
            instrument=intent.instrument,
            side=intent.side,
            order_type=intent.order_type,
            status=status,
            quantity=intent.quantity,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price,
            message=message,
        )

    def _save_order(self, client_order_key: str, order: OrderEvent) -> None:
        self.repository.save_order(client_order_key, order)
        self._orders[client_order_key] = order

    def _rejection_reason(self, intent: OrderIntent) -> str | None:
        if self.config.reject_non_market_orders and intent.order_type != OrderType.MARKET:
            return "non-market orders disabled"
        if self.config.max_quantity is not None and intent.quantity > self.config.max_quantity:
            return "quantity exceeds paper execution limit"
        return None

    def _apply_fill(self, fill: FillEvent) -> None:
        previous = self._positions.get(fill.instrument)
        previous_quantity = previous.quantity if previous is not None else Decimal("0")
        previous_average = (
            previous.average_price or Decimal("0") if previous is not None else Decimal("0")
        )
        signed_fill_quantity = fill.quantity if fill.side == Side.BUY else -fill.quantity
        new_quantity = previous_quantity + signed_fill_quantity
        average_price = calculate_average_price(
            previous_quantity=previous_quantity,
            previous_average=previous_average,
            fill_quantity=signed_fill_quantity,
            fill_price=fill.price,
            new_quantity=new_quantity,
        )
        position = PositionSnapshot(
            timestamp=fill.timestamp,
            correlation_id=f"position-{fill.correlation_id}",
            source=PAPER_SOURCE,
            account_id=self.config.account_id,
            instrument=fill.instrument,
            quantity=new_quantity,
            average_price=average_price,
            mark_price=fill.price,
            exposure=new_quantity * fill.price,
        )
        self._positions[fill.instrument] = position
        self.repository.save_position(position)

    def _timestamp(self) -> datetime:
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("execution clock must return timezone-aware timestamps")
        return timestamp.astimezone(UTC)


def normalize_order_intent(intent: OrderIntent, config: PaperExecutionConfig) -> OrderIntent:
    """Normalize price and quantity increments before submission."""

    quantity = quantize_increment(intent.quantity, config.quantity_increment)
    limit_price = (
        quantize_increment(intent.limit_price, config.price_increment)
        if intent.limit_price is not None
        else None
    )
    stop_price = (
        quantize_increment(intent.stop_price, config.price_increment)
        if intent.stop_price is not None
        else None
    )
    return intent.model_copy(
        update={
            "quantity": quantity,
            "limit_price": limit_price,
            "stop_price": stop_price,
        }
    )


def quantize_increment(value: Decimal, increment: Decimal) -> Decimal:
    """Round a positive value to the nearest configured increment."""

    if increment <= Decimal("0"):
        raise ValueError("increment must be positive")
    units = (value / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return units * increment


def execution_price(intent: OrderIntent, config: PaperExecutionConfig) -> Decimal:
    """Resolve a deterministic paper fill price."""

    if intent.order_type == OrderType.MARKET:
        return config.default_fill_price
    return intent.limit_price or intent.stop_price or config.default_fill_price


def calculate_average_price(
    *,
    previous_quantity: Decimal,
    previous_average: Decimal,
    fill_quantity: Decimal,
    fill_price: Decimal,
    new_quantity: Decimal,
) -> Decimal | None:
    """Calculate simple average price for same-direction paper positions."""

    if new_quantity == Decimal("0"):
        return None
    if previous_quantity == Decimal("0") or (previous_quantity > 0) != (new_quantity > 0):
        return fill_price
    if (previous_quantity > 0) == (fill_quantity > 0):
        return (
            (abs(previous_quantity) * previous_average) + (abs(fill_quantity) * fill_price)
        ) / abs(new_quantity)
    return previous_average
