"""Execution repository implementations."""

from __future__ import annotations

from aurus.common.schemas import FillEvent, OrderEvent, PositionSnapshot


class InMemoryExecutionRepository:
    """In-memory repository useful for tests and paper execution."""

    def __init__(self) -> None:
        self._orders: dict[str, OrderEvent] = {}
        self._fills: list[FillEvent] = []
        self._positions: dict[tuple[str, str], PositionSnapshot] = {}

    def save_order(self, client_order_key: str, order: OrderEvent) -> None:
        self._orders[client_order_key] = order

    def get_order(self, client_order_key: str) -> OrderEvent | None:
        return self._orders.get(client_order_key)

    def list_orders(self) -> tuple[tuple[str, OrderEvent], ...]:
        return tuple(sorted(self._orders.items(), key=lambda item: item[0]))

    def save_fill(self, fill: FillEvent) -> None:
        self._fills.append(fill)

    def list_fills(self) -> tuple[FillEvent, ...]:
        return tuple(self._fills)

    def save_position(self, position: PositionSnapshot) -> None:
        self._positions[(position.account_id, position.instrument)] = position

    def list_positions(self) -> tuple[PositionSnapshot, ...]:
        return tuple(sorted(self._positions.values(), key=lambda item: item.instrument))

