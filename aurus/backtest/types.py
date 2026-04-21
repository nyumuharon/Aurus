"""Typed backtest result structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from aurus.common.schemas import (
    BarEvent,
    DomainModel,
    FillEvent,
    OrderEvent,
    OrderIntent,
    PositionSnapshot,
    RiskDecision,
    SignalEvent,
)


@dataclass(frozen=True)
class BacktestConfig:
    """Deterministic execution assumptions for a backtest run."""

    initial_cash: Decimal = Decimal("100000")
    default_quantity: Decimal = Decimal("1")
    spread: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    entry_slippage: Decimal | None = None
    exit_slippage: Decimal | None = None
    spread_multiplier: Decimal = Decimal("1")
    commission_per_fill: Decimal = Decimal("0")
    account_id: str = "backtest"
    record_events: bool = True
    stop_tightening_enabled: bool = False
    breakeven_trigger_r: Decimal = Decimal("0.5")
    trailing_trigger_r: Decimal = Decimal("1.0")
    trailing_stop_r: Decimal = Decimal("0.25")


@dataclass(frozen=True)
class TradeRecord:
    """Closed trade ledger row."""

    trade_id: str
    instrument: str
    side: str
    quantity: Decimal
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
    exit_reason: str


@dataclass(frozen=True)
class EquityPoint:
    """Point-in-time account equity after processing a bar."""

    timestamp: datetime
    cash: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    equity: Decimal


@dataclass(frozen=True)
class BacktestResult:
    """Complete deterministic output from a backtest run."""

    trades: tuple[TradeRecord, ...]
    equity_curve: tuple[EquityPoint, ...]
    event_log: tuple[str, ...]
    events: tuple[DomainModel, ...]


@dataclass
class OpenPosition:
    """Internal mutable position state for the simulator."""

    instrument: str
    side: str
    quantity: Decimal
    entry_timestamp: datetime
    entry_price: Decimal
    entry_fill_id: str
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    initial_risk_per_unit: Decimal | None = None
    commission: Decimal = Decimal("0")


@dataclass
class BacktestState:
    """Internal mutable engine state."""

    cash: Decimal
    realized_pnl: Decimal = Decimal("0")
    position: OpenPosition | None = None
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    events: list[DomainModel] = field(default_factory=list)
    bars: list[BarEvent] = field(default_factory=list)
    sequence: int = 0

    def next_id(self, prefix: str) -> str:
        self.sequence += 1
        return f"{prefix}-{self.sequence:08d}"


BacktestEvent = (
    BarEvent
    | SignalEvent
    | RiskDecision
    | OrderIntent
    | OrderEvent
    | FillEvent
    | PositionSnapshot
)
