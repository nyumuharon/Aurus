"""Exhaustive rule tests for the pure risk kernel."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from aurus.common.schemas import Side, SignalEvent
from aurus.risk import NewsBlackoutWindow, RiskConfig, RiskEvaluation, RiskKernel, RiskSnapshot
from pydantic import JsonValue

NOW = datetime(2026, 4, 21, 10, 0, tzinfo=UTC)


def config(
    *,
    max_daily_realized_loss: Decimal = Decimal("500"),
    max_total_drawdown: Decimal = Decimal("1000"),
    max_trades_per_day: int = 3,
    max_spread: Decimal = Decimal("0.50"),
    blocked_sessions: frozenset[str] = frozenset({"rollover"}),
    max_consecutive_losses: int = 2,
    require_stop_loss: bool = True,
    max_concurrent_positions: int = 1,
    news_blackout_windows: tuple[NewsBlackoutWindow, ...] = (),
) -> RiskConfig:
    return RiskConfig(
        max_daily_realized_loss=max_daily_realized_loss,
        max_total_drawdown=max_total_drawdown,
        max_trades_per_day=max_trades_per_day,
        max_spread=max_spread,
        blocked_sessions=blocked_sessions,
        max_consecutive_losses=max_consecutive_losses,
        require_stop_loss=require_stop_loss,
        max_concurrent_positions=max_concurrent_positions,
        news_blackout_windows=news_blackout_windows,
    )


def snapshot(
    *,
    timestamp: datetime = NOW,
    realized_pnl_today: Decimal = Decimal("0"),
    current_equity: Decimal = Decimal("100000"),
    peak_equity: Decimal = Decimal("100000"),
    trades_today: int = 0,
    spread: Decimal = Decimal("0.20"),
    session: str = "london",
    seen_signal_ids: frozenset[str] = frozenset(),
    consecutive_losses: int = 0,
    open_positions: int = 0,
) -> RiskSnapshot:
    return RiskSnapshot(
        timestamp=timestamp,
        realized_pnl_today=realized_pnl_today,
        current_equity=current_equity,
        peak_equity=peak_equity,
        trades_today=trades_today,
        spread=spread,
        session=session,
        seen_signal_ids=seen_signal_ids,
        consecutive_losses=consecutive_losses,
        open_positions=open_positions,
    )


def signal(
    *,
    timestamp: datetime = NOW,
    correlation_id: str = "corr-1",
    signal_id: str = "signal-1",
    strategy_id: str = "risk-test",
    instrument: str = "XAU/USD",
    side: Side = Side.BUY,
    strength: Decimal = Decimal("1"),
    features: dict[str, JsonValue] | None = None,
) -> SignalEvent:
    return SignalEvent(
        timestamp=timestamp,
        correlation_id=correlation_id,
        signal_id=signal_id,
        strategy_id=strategy_id,
        instrument=instrument,
        side=side,
        strength=strength,
        features=features if features is not None else {"stop_loss": "2380.00"},
    )


def evaluate(
    *,
    risk_config: RiskConfig | None = None,
    risk_snapshot: RiskSnapshot | None = None,
    risk_signal: SignalEvent | None = None,
) -> RiskEvaluation:
    return RiskKernel(risk_config or config()).evaluate_structured(
        risk_signal or signal(),
        risk_snapshot or snapshot(),
    )


def assert_denied_for(
    reason: str,
    *,
    risk_config: RiskConfig | None = None,
    risk_snapshot: RiskSnapshot | None = None,
    risk_signal: SignalEvent | None = None,
) -> None:
    result = evaluate(
        risk_config=risk_config,
        risk_snapshot=risk_snapshot,
        risk_signal=risk_signal,
    )

    assert not result.allowed
    assert not result.decision.approved
    assert result.decision.action == "reject"
    assert reason in result.reasons
    assert reason in result.decision.reason
    metadata_reasons = result.decision.metadata["reasons"]
    assert isinstance(metadata_reasons, list)
    assert reason in metadata_reasons


def test_all_rules_allow_valid_signal() -> None:
    result = evaluate()

    assert result.allowed
    assert result.decision.approved
    assert result.decision.action == "approve"
    assert result.decision.reason == "allowed"
    assert len(result.rule_results) == 10


def test_max_daily_realized_loss_denies_at_limit() -> None:
    assert_denied_for(
        "max daily realized loss reached",
        risk_snapshot=snapshot(realized_pnl_today=Decimal("-500")),
    )


def test_max_daily_realized_loss_allows_before_limit() -> None:
    result = evaluate(risk_snapshot=snapshot(realized_pnl_today=Decimal("-499.99")))
    assert result.allowed


def test_max_total_drawdown_denies_over_limit() -> None:
    assert_denied_for(
        "max total drawdown reached",
        risk_snapshot=snapshot(
            peak_equity=Decimal("100000"),
            current_equity=Decimal("98999.99"),
        ),
    )


def test_max_total_drawdown_allows_at_limit() -> None:
    result = evaluate(
        risk_snapshot=snapshot(
            peak_equity=Decimal("100000"),
            current_equity=Decimal("99000"),
        )
    )
    assert result.allowed


def test_max_trades_per_day_denies_at_limit() -> None:
    assert_denied_for(
        "max trades per day reached",
        risk_snapshot=snapshot(trades_today=3),
    )


def test_max_trades_per_day_allows_below_limit() -> None:
    result = evaluate(risk_snapshot=snapshot(trades_today=2))
    assert result.allowed


def test_max_spread_threshold_denies_above_limit() -> None:
    assert_denied_for(
        "spread threshold exceeded",
        risk_snapshot=snapshot(spread=Decimal("0.51")),
    )


def test_max_spread_threshold_allows_at_limit() -> None:
    result = evaluate(risk_snapshot=snapshot(spread=Decimal("0.50")))
    assert result.allowed


def test_blocked_session_rollover_denies() -> None:
    assert_denied_for(
        "session blocked: rollover",
        risk_snapshot=snapshot(session="rollover"),
    )


def test_allowed_session_passes() -> None:
    result = evaluate(risk_snapshot=snapshot(session="new_york"))
    assert result.allowed


def test_duplicate_signal_suppression_denies_seen_signal_id() -> None:
    assert_denied_for(
        "duplicate signal suppressed",
        risk_snapshot=snapshot(seen_signal_ids=frozenset({"signal-1"})),
    )


def test_new_signal_id_passes_duplicate_check() -> None:
    result = evaluate(risk_snapshot=snapshot(seen_signal_ids=frozenset({"other-signal"})))
    assert result.allowed


def test_max_consecutive_losses_cooldown_denies_at_limit() -> None:
    assert_denied_for(
        "max consecutive losses cooldown active",
        risk_snapshot=snapshot(consecutive_losses=2),
    )


def test_max_consecutive_losses_allows_below_limit() -> None:
    result = evaluate(risk_snapshot=snapshot(consecutive_losses=1))
    assert result.allowed


def test_mandatory_stop_loss_denies_entry_without_stop() -> None:
    assert_denied_for(
        "stop loss required",
        risk_signal=signal(features={}),
    )


def test_mandatory_stop_loss_allows_flat_exit_without_stop() -> None:
    result = evaluate(risk_signal=signal(side=Side.FLAT, features={}))
    assert result.allowed


def test_mandatory_stop_loss_can_be_disabled() -> None:
    result = evaluate(risk_config=config(require_stop_loss=False), risk_signal=signal(features={}))
    assert result.allowed


def test_max_concurrent_positions_denies_new_entry_at_limit() -> None:
    assert_denied_for(
        "max concurrent positions reached",
        risk_snapshot=snapshot(open_positions=1),
    )


def test_max_concurrent_positions_allows_flat_exit_at_limit() -> None:
    result = evaluate(risk_snapshot=snapshot(open_positions=1), risk_signal=signal(side=Side.FLAT))
    assert result.allowed


def test_news_blackout_window_denies_signal_inside_window() -> None:
    window = NewsBlackoutWindow(
        start=NOW - timedelta(minutes=5),
        end=NOW + timedelta(minutes=5),
        label="high-impact-usd",
    )

    assert_denied_for(
        "news blackout active: high-impact-usd",
        risk_config=config(news_blackout_windows=(window,)),
    )


def test_news_blackout_window_allows_signal_outside_window() -> None:
    window = NewsBlackoutWindow(
        start=NOW + timedelta(minutes=5),
        end=NOW + timedelta(minutes=10),
        label="high-impact-usd",
    )

    result = evaluate(risk_config=config(news_blackout_windows=(window,)))
    assert result.allowed


def test_multiple_denials_are_reported_together() -> None:
    result = evaluate(
        risk_snapshot=snapshot(
            realized_pnl_today=Decimal("-500"),
            spread=Decimal("1.00"),
            session="rollover",
        ),
        risk_signal=signal(features={}),
    )

    assert not result.allowed
    assert result.reasons == (
        "max daily realized loss reached",
        "spread threshold exceeded",
        "session blocked: rollover",
        "stop loss required",
    )


def test_signal_timestamp_must_be_utc_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        signal(timestamp=datetime(2026, 4, 21, 10, 0))
