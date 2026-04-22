"""Execution repository implementations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


class JsonlExecutionRepository:
    """Append-only JSONL repository for restart-safe paper execution state."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.orders_path = self.root / "orders.jsonl"
        self.fills_path = self.root / "fills.jsonl"
        self.positions_path = self.root / "positions.jsonl"

    def save_order(self, client_order_key: str, order: OrderEvent) -> None:
        self._append_json(
            self.orders_path,
            {
                "client_order_key": client_order_key,
                "order": order.model_dump(mode="json"),
            },
        )

    def get_order(self, client_order_key: str) -> OrderEvent | None:
        return dict(self.list_orders()).get(client_order_key)

    def list_orders(self) -> tuple[tuple[str, OrderEvent], ...]:
        orders: dict[str, OrderEvent] = {}
        for row in self._read_jsonl(self.orders_path):
            key = str(row["client_order_key"])
            orders[key] = OrderEvent.model_validate(row["order"])
        return tuple(sorted(orders.items(), key=lambda item: item[0]))

    def save_fill(self, fill: FillEvent) -> None:
        self._append_json(self.fills_path, fill.model_dump(mode="json"))

    def list_fills(self) -> tuple[FillEvent, ...]:
        return tuple(FillEvent.model_validate(row) for row in self._read_jsonl(self.fills_path))

    def save_position(self, position: PositionSnapshot) -> None:
        self._append_json(self.positions_path, position.model_dump(mode="json"))

    def list_positions(self) -> tuple[PositionSnapshot, ...]:
        positions: dict[tuple[str, str], PositionSnapshot] = {}
        for row in self._read_jsonl(self.positions_path):
            position = PositionSnapshot.model_validate(row)
            positions[(position.account_id, position.instrument)] = position
        return tuple(sorted(positions.values(), key=lambda item: item.instrument))

    def _append_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    def _read_jsonl(self, path: Path) -> tuple[dict[str, Any], ...]:
        if not path.exists():
            return ()
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                payload = line.strip()
                if payload:
                    row = json.loads(payload)
                    if not isinstance(row, dict):
                        raise ValueError(f"invalid JSONL repository row in {path}")
                    rows.append(row)
        return tuple(rows)
