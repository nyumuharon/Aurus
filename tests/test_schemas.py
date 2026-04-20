"""Validation and serialization tests for canonical domain schemas."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from aurus.common.schemas import (
    AlertSeverity,
    BarEvent,
    FillEvent,
    OrderEvent,
    OrderIntent,
    OrderStatus,
    OrderType,
    PositionSnapshot,
    RiskAction,
    RiskDecision,
    Side,
    SignalEvent,
    SourceMetadata,
    SystemAlert,
    TickEvent,
    domain_from_json,
    from_json,
    to_json,
)
from pydantic import ValidationError

SOURCE = SourceMetadata(name="recorded-feed", kind="market_data", version="0.1.0")
TS = datetime(2026, 4, 20, 9, 30, tzinfo=timezone(timedelta(hours=3)))
UTC_TS = datetime(2026, 4, 20, 6, 30, tzinfo=UTC)


def test_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TickEvent(
            timestamp=datetime(2026, 4, 20, 9, 30),
            correlation_id="corr-1",
            source=SOURCE,
            bid=Decimal("2380.10"),
            ask=Decimal("2380.30"),
        )


def test_timestamp_is_normalized_to_utc() -> None:
    event = TickEvent(
        timestamp=TS,
        correlation_id="corr-1",
        source=SOURCE,
        bid=Decimal("2380.10"),
        ask=Decimal("2380.30"),
    )

    assert event.timestamp == UTC_TS


def test_tick_rejects_crossed_market() -> None:
    with pytest.raises(ValidationError, match="bid must be less than or equal to ask"):
        TickEvent(
            timestamp=UTC_TS,
            correlation_id="corr-1",
            source=SOURCE,
            bid=Decimal("2380.40"),
            ask=Decimal("2380.30"),
        )


def test_bar_rejects_inconsistent_ohlc() -> None:
    with pytest.raises(ValidationError, match="open and close must be within low/high bounds"):
        BarEvent(
            timestamp=UTC_TS,
            correlation_id="corr-1",
            source=SOURCE,
            timeframe="1m",
            open=Decimal("2380.10"),
            high=Decimal("2381.00"),
            low=Decimal("2380.20"),
            close=Decimal("2380.50"),
            volume=Decimal("12.5"),
        )


def test_risk_decision_must_match_approval_state() -> None:
    with pytest.raises(ValidationError, match="unapproved decisions must have reject action"):
        RiskDecision(
            timestamp=UTC_TS,
            correlation_id="corr-1",
            source=SOURCE,
            decision_id="risk-1",
            approved=False,
            action=RiskAction.APPROVE,
            reason="limit check failed",
        )


def test_order_intent_requires_prices_for_limit_and_stop_orders() -> None:
    with pytest.raises(ValidationError, match="limit orders require limit_price"):
        OrderIntent(
            timestamp=UTC_TS,
            correlation_id="corr-1",
            source=SOURCE,
            intent_id="intent-1",
            risk_decision_id="risk-1",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
        )


def test_order_event_rejects_overfill() -> None:
    with pytest.raises(ValidationError, match="filled_quantity cannot exceed quantity"):
        OrderEvent(
            timestamp=UTC_TS,
            correlation_id="corr-1",
            source=SOURCE,
            order_id="order-1",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.PARTIALLY_FILLED,
            quantity=Decimal("1"),
            filled_quantity=Decimal("2"),
        )


def test_all_schemas_round_trip_with_deterministic_json() -> None:
    models = [
        TickEvent(
            timestamp=TS,
            correlation_id="corr-tick",
            source=SOURCE,
            bid=Decimal("2380.10"),
            ask=Decimal("2380.30"),
            metadata={"session": "ny"},
        ),
        BarEvent(
            timestamp=TS,
            correlation_id="corr-bar",
            source=SOURCE,
            timeframe="1m",
            open=Decimal("2380.10"),
            high=Decimal("2381.00"),
            low=Decimal("2380.00"),
            close=Decimal("2380.50"),
            volume=Decimal("12.5"),
        ),
        SignalEvent(
            timestamp=TS,
            correlation_id="corr-signal",
            source=SOURCE,
            signal_id="signal-1",
            strategy_id="baseline-research",
            side=Side.BUY,
            strength=Decimal("0.70"),
            reason="placeholder hypothesis output",
            features={"bar_count": 20},
        ),
        RiskDecision(
            timestamp=TS,
            correlation_id="corr-risk",
            source=SOURCE,
            decision_id="risk-1",
            signal_id="signal-1",
            approved=True,
            action=RiskAction.APPROVE,
            reason="within configured limits",
            max_quantity=Decimal("1"),
        ),
        OrderIntent(
            timestamp=TS,
            correlation_id="corr-intent",
            source=SOURCE,
            intent_id="intent-1",
            risk_decision_id="risk-1",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            limit_price=Decimal("2380.30"),
        ),
        OrderEvent(
            timestamp=TS,
            correlation_id="corr-order",
            source=SOURCE,
            order_id="order-1",
            intent_id="intent-1",
            broker_order_id="broker-order-1",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            status=OrderStatus.ACCEPTED,
            quantity=Decimal("1"),
        ),
        FillEvent(
            timestamp=TS,
            correlation_id="corr-fill",
            source=SOURCE,
            fill_id="fill-1",
            order_id="order-1",
            side=Side.BUY,
            quantity=Decimal("1"),
            price=Decimal("2380.20"),
            commission=Decimal("0.50"),
        ),
        PositionSnapshot(
            timestamp=TS,
            correlation_id="corr-position",
            source=SOURCE,
            account_id="account-1",
            quantity=Decimal("1"),
            average_price=Decimal("2380.20"),
            mark_price=Decimal("2380.40"),
            unrealized_pnl=Decimal("0.20"),
        ),
        SystemAlert(
            timestamp=TS,
            correlation_id="corr-alert",
            source=SourceMetadata(name="risk-monitor", kind="ops"),
            alert_id="alert-1",
            severity=AlertSeverity.WARNING,
            component="risk",
            message="drawdown threshold warning",
            details={"threshold": "warning"},
        ),
    ]

    for model in models:
        payload = to_json(model)
        assert payload == to_json(model)
        assert "\n" not in payload

        restored = from_json(type(model), payload)
        assert restored == model
        assert restored.to_json() == payload
        assert domain_from_json(payload) == model
