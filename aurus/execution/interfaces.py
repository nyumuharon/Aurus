"""Broker execution adapter interfaces."""

from __future__ import annotations

from typing import Protocol

from aurus.common.schemas import FillEvent, OrderEvent, OrderIntent, PositionSnapshot


class ExecutionAdapter(Protocol):
    """Broker-neutral execution adapter interface."""

    def submit_order(self, intent: OrderIntent, *, client_order_key: str) -> OrderEvent:
        """Submit an order idempotently using a client order key."""

    def get_order(self, client_order_key: str) -> OrderEvent | None:
        """Return the order associated with a client order key, if known."""

    def list_fills(self) -> tuple[FillEvent, ...]:
        """Return known fills."""

    def positions(self) -> tuple[PositionSnapshot, ...]:
        """Return current position snapshots."""

    def reconcile(self) -> None:
        """Reload persisted state and reconcile in-memory views."""


class ExecutionRepository(Protocol):
    """Persistence boundary for restart-safe paper/live adapters."""

    def save_order(self, client_order_key: str, order: OrderEvent) -> None:
        """Persist an order keyed by client order key."""

    def get_order(self, client_order_key: str) -> OrderEvent | None:
        """Load an order by client order key."""

    def list_orders(self) -> tuple[tuple[str, OrderEvent], ...]:
        """Load all persisted orders and their client keys."""

    def save_fill(self, fill: FillEvent) -> None:
        """Persist a fill."""

    def list_fills(self) -> tuple[FillEvent, ...]:
        """Load all persisted fills."""

    def save_position(self, position: PositionSnapshot) -> None:
        """Persist a position snapshot."""

    def list_positions(self) -> tuple[PositionSnapshot, ...]:
        """Load all latest position snapshots."""

