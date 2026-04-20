"""Canonical domain schemas for aurus events and state snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

SchemaT = TypeVar("SchemaT", bound="DomainModel")


class EventKind(StrEnum):
    """Canonical event type names for serialized payloads."""

    TICK = "tick"
    BAR = "bar"
    SIGNAL = "signal"
    RISK_DECISION = "risk_decision"
    ORDER_INTENT = "order_intent"
    ORDER_EVENT = "order_event"
    FILL = "fill"
    POSITION_SNAPSHOT = "position_snapshot"
    SYSTEM_ALERT = "system_alert"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"
    FLAT = "flat"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(StrEnum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    DAY = "day"


class RiskAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REDUCE = "reduce"


class OrderStatus(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SourceMetadata(BaseModel):
    """Metadata that identifies where a domain event came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    version: str | None = None
    instance_id: str | None = None


class DomainModel(BaseModel):
    """Base class for deterministic domain schema serialization."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        use_enum_values=True,
    )

    event_kind: EventKind
    timestamp: datetime
    correlation_id: str = Field(min_length=1)
    source: SourceMetadata | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def require_aware_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)

    def to_json(self) -> str:
        """Serialize with stable key ordering and compact separators."""

        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls: type[SchemaT], payload: str) -> SchemaT:
        """Deserialize a JSON payload into this schema type."""

        return cls.model_validate_json(payload)


class TickEvent(DomainModel):
    event_kind: EventKind = EventKind.TICK
    instrument: str = Field(default="XAU/USD", min_length=1)
    bid: Decimal = Field(gt=Decimal("0"))
    ask: Decimal = Field(gt=Decimal("0"))
    bid_size: Decimal | None = Field(default=None, ge=Decimal("0"))
    ask_size: Decimal | None = Field(default=None, ge=Decimal("0"))
    last: Decimal | None = Field(default=None, gt=Decimal("0"))
    sequence: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_spread(self) -> TickEvent:
        if self.bid > self.ask:
            raise ValueError("bid must be less than or equal to ask")
        return self


class BarEvent(DomainModel):
    event_kind: EventKind = EventKind.BAR
    instrument: str = Field(default="XAU/USD", min_length=1)
    timeframe: str = Field(min_length=1)
    open: Decimal = Field(gt=Decimal("0"))
    high: Decimal = Field(gt=Decimal("0"))
    low: Decimal = Field(gt=Decimal("0"))
    close: Decimal = Field(gt=Decimal("0"))
    volume: Decimal = Field(ge=Decimal("0"))
    spread: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_ohlc_bounds(self) -> BarEvent:
        prices = (self.open, self.close)
        if self.low > self.high:
            raise ValueError("low must be less than or equal to high")
        if any(price < self.low or price > self.high for price in prices):
            raise ValueError("open and close must be within low/high bounds")
        return self


class SignalEvent(DomainModel):
    event_kind: EventKind = EventKind.SIGNAL
    signal_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    instrument: str = Field(default="XAU/USD", min_length=1)
    side: Side
    strength: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    reason: str | None = None
    features: dict[str, JsonValue] = Field(default_factory=dict)


class RiskDecision(DomainModel):
    event_kind: EventKind = EventKind.RISK_DECISION
    decision_id: str = Field(min_length=1)
    signal_id: str | None = None
    approved: bool
    action: RiskAction
    reason: str
    max_quantity: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_decision_consistency(self) -> RiskDecision:
        if self.approved and self.action == RiskAction.REJECT:
            raise ValueError("approved decisions cannot have reject action")
        if not self.approved and self.action != RiskAction.REJECT:
            raise ValueError("unapproved decisions must have reject action")
        return self


class OrderIntent(DomainModel):
    event_kind: EventKind = EventKind.ORDER_INTENT
    intent_id: str = Field(min_length=1)
    risk_decision_id: str = Field(min_length=1)
    instrument: str = Field(default="XAU/USD", min_length=1)
    side: Side
    order_type: OrderType
    quantity: Decimal = Field(gt=Decimal("0"))
    limit_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    stop_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    time_in_force: TimeInForce = TimeInForce.GTC

    @model_validator(mode="after")
    def validate_order_prices(self) -> OrderIntent:
        if self.side == Side.FLAT:
            raise ValueError("order side cannot be flat")
        if self.order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT} and self.limit_price is None:
            raise ValueError("limit orders require limit_price")
        if self.order_type in {OrderType.STOP, OrderType.STOP_LIMIT} and self.stop_price is None:
            raise ValueError("stop orders require stop_price")
        return self


class OrderEvent(DomainModel):
    event_kind: EventKind = EventKind.ORDER_EVENT
    order_id: str = Field(min_length=1)
    intent_id: str | None = None
    broker_order_id: str | None = None
    instrument: str = Field(default="XAU/USD", min_length=1)
    side: Side
    order_type: OrderType
    status: OrderStatus
    quantity: Decimal = Field(gt=Decimal("0"))
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    average_fill_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    message: str | None = None

    @model_validator(mode="after")
    def validate_fill_quantity(self) -> OrderEvent:
        if self.side == Side.FLAT:
            raise ValueError("order side cannot be flat")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        return self


class FillEvent(DomainModel):
    event_kind: EventKind = EventKind.FILL
    fill_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    broker_fill_id: str | None = None
    instrument: str = Field(default="XAU/USD", min_length=1)
    side: Side
    quantity: Decimal = Field(gt=Decimal("0"))
    price: Decimal = Field(gt=Decimal("0"))
    commission: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    liquidity: str | None = None

    @model_validator(mode="after")
    def validate_fill_side(self) -> FillEvent:
        if self.side == Side.FLAT:
            raise ValueError("fill side cannot be flat")
        return self


class PositionSnapshot(DomainModel):
    event_kind: EventKind = EventKind.POSITION_SNAPSHOT
    account_id: str = Field(min_length=1)
    instrument: str = Field(default="XAU/USD", min_length=1)
    quantity: Decimal
    average_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    mark_price: Decimal = Field(gt=Decimal("0"))
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    exposure: Decimal | None = None


class SystemAlert(DomainModel):
    event_kind: EventKind = EventKind.SYSTEM_ALERT
    alert_id: str = Field(min_length=1)
    severity: AlertSeverity
    component: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, JsonValue] = Field(default_factory=dict)


DOMAIN_SCHEMA_TYPES: dict[EventKind, type[DomainModel]] = {
    EventKind.TICK: TickEvent,
    EventKind.BAR: BarEvent,
    EventKind.SIGNAL: SignalEvent,
    EventKind.RISK_DECISION: RiskDecision,
    EventKind.ORDER_INTENT: OrderIntent,
    EventKind.ORDER_EVENT: OrderEvent,
    EventKind.FILL: FillEvent,
    EventKind.POSITION_SNAPSHOT: PositionSnapshot,
    EventKind.SYSTEM_ALERT: SystemAlert,
}


def to_json(model: DomainModel) -> str:
    """Serialize any aurus domain model to deterministic JSON."""

    return model.to_json()


def from_json(schema_type: type[SchemaT], payload: str) -> SchemaT:
    """Deserialize deterministic JSON into the requested schema type."""

    return schema_type.from_json(payload)


def domain_from_json(payload: str) -> DomainModel:
    """Deserialize a domain payload using its canonical event kind."""

    raw_event_kind = json.loads(payload).get("event_kind")
    event_kind = EventKind(raw_event_kind)
    return DOMAIN_SCHEMA_TYPES[event_kind].from_json(payload)
