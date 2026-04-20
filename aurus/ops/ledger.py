"""Trade ledger persistence abstractions."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from aurus.backtest.types import TradeRecord

TRADE_LEDGER_COLUMNS = (
    "trade_id",
    "instrument",
    "side",
    "quantity",
    "entry_timestamp",
    "exit_timestamp",
    "entry_price",
    "exit_price",
    "gross_pnl",
    "commission",
    "net_pnl",
    "exit_reason",
)


class TradeLedgerRepository(Protocol):
    """Persistence boundary for closed trade records."""

    def append(self, trade: TradeRecord) -> None:
        """Append one trade."""

    def append_many(self, trades: tuple[TradeRecord, ...]) -> None:
        """Append several trades."""

    def read_all(self) -> tuple[TradeRecord, ...]:
        """Read all persisted trades."""


class InMemoryTradeLedgerRepository:
    """In-memory trade ledger repository for tests."""

    def __init__(self) -> None:
        self._trades: list[TradeRecord] = []

    def append(self, trade: TradeRecord) -> None:
        self._trades.append(trade)

    def append_many(self, trades: tuple[TradeRecord, ...]) -> None:
        self._trades.extend(trades)

    def read_all(self) -> tuple[TradeRecord, ...]:
        return tuple(self._trades)


class CsvTradeLedgerRepository:
    """Append-only CSV trade ledger repository."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, trade: TradeRecord) -> None:
        self.append_many((trade,))

    def append_many(self, trades: tuple[TradeRecord, ...]) -> None:
        if not trades:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.path.exists()
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRADE_LEDGER_COLUMNS)
            if write_header:
                writer.writeheader()
            for trade in trades:
                writer.writerow(trade_to_row(trade))

    def read_all(self) -> tuple[TradeRecord, ...]:
        if not self.path.exists():
            return ()
        with self.path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return tuple(row_to_trade(row) for row in reader)


def trade_to_row(trade: TradeRecord) -> dict[str, str]:
    """Serialize a trade record to CSV-safe strings."""

    return {
        "trade_id": trade.trade_id,
        "instrument": trade.instrument,
        "side": trade.side,
        "quantity": str(trade.quantity),
        "entry_timestamp": trade.entry_timestamp.isoformat(),
        "exit_timestamp": trade.exit_timestamp.isoformat(),
        "entry_price": str(trade.entry_price),
        "exit_price": str(trade.exit_price),
        "gross_pnl": str(trade.gross_pnl),
        "commission": str(trade.commission),
        "net_pnl": str(trade.net_pnl),
        "exit_reason": trade.exit_reason,
    }


def row_to_trade(row: dict[str, str]) -> TradeRecord:
    """Deserialize a CSV row into a trade record."""

    return TradeRecord(
        trade_id=row["trade_id"],
        instrument=row["instrument"],
        side=row["side"],
        quantity=Decimal(row["quantity"]),
        entry_timestamp=datetime.fromisoformat(row["entry_timestamp"]),
        exit_timestamp=datetime.fromisoformat(row["exit_timestamp"]),
        entry_price=Decimal(row["entry_price"]),
        exit_price=Decimal(row["exit_price"]),
        gross_pnl=Decimal(row["gross_pnl"]),
        commission=Decimal(row["commission"]),
        net_pnl=Decimal(row["net_pnl"]),
        exit_reason=row["exit_reason"],
    )

