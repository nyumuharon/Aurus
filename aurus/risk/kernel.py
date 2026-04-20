"""Pure deterministic risk kernel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from aurus.common.schemas import RiskAction, RiskDecision, Side, SignalEvent, SourceMetadata

RISK_SOURCE = SourceMetadata(name="aurus-risk-kernel", kind="risk_kernel")


@dataclass(frozen=True)
class NewsBlackoutWindow:
    """Configured news blackout interval.

    This is a placeholder domain hook. Upstream adapters are responsible for
    building these windows from a trusted calendar source.
    """

    start: datetime
    end: datetime
    label: str

    def contains(self, timestamp: datetime) -> bool:
        return self.start <= timestamp < self.end


@dataclass(frozen=True)
class RiskConfig:
    """Explicit risk limits for the pure risk kernel."""

    max_daily_realized_loss: Decimal
    max_total_drawdown: Decimal
    max_trades_per_day: int
    max_spread: Decimal
    blocked_sessions: frozenset[str] = frozenset({"rollover"})
    max_consecutive_losses: int = 3
    require_stop_loss: bool = True
    max_concurrent_positions: int = 1
    news_blackout_windows: tuple[NewsBlackoutWindow, ...] = ()


@dataclass(frozen=True)
class RiskSnapshot:
    """Current deterministic state needed to evaluate a signal."""

    timestamp: datetime
    realized_pnl_today: Decimal
    current_equity: Decimal
    peak_equity: Decimal
    trades_today: int
    spread: Decimal
    session: str
    seen_signal_ids: frozenset[str] = frozenset()
    consecutive_losses: int = 0
    open_positions: int = 0


@dataclass(frozen=True)
class RuleResult:
    """Single risk rule result."""

    code: str
    allowed: bool
    reason: str


@dataclass(frozen=True)
class RiskEvaluation:
    """Structured result before conversion to canonical RiskDecision."""

    allowed: bool
    reasons: tuple[str, ...]
    rule_results: tuple[RuleResult, ...]
    decision: RiskDecision


class RiskKernel:
    """Stateless risk evaluator."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def evaluate(self, signal: SignalEvent, snapshot: RiskSnapshot) -> RiskDecision:
        """Evaluate a signal and return the canonical domain decision."""

        return self.evaluate_structured(signal, snapshot).decision

    def evaluate_structured(
        self,
        signal: SignalEvent,
        snapshot: RiskSnapshot,
    ) -> RiskEvaluation:
        """Evaluate all rules and preserve per-rule diagnostics."""

        rule_results = tuple(
            check(signal, snapshot, self.config)
            for check in (
                check_max_daily_realized_loss,
                check_max_total_drawdown,
                check_max_trades_per_day,
                check_max_spread,
                check_blocked_session,
                check_duplicate_signal,
                check_max_consecutive_losses,
                check_mandatory_stop_loss,
                check_max_concurrent_positions,
                check_news_blackout,
            )
        )
        denied = tuple(result for result in rule_results if not result.allowed)
        allowed = not denied
        reasons = tuple(result.reason for result in denied) or ("allowed",)
        decision = RiskDecision(
            timestamp=snapshot.timestamp,
            correlation_id=signal.correlation_id,
            source=RISK_SOURCE,
            decision_id=f"risk-{signal.signal_id}",
            signal_id=signal.signal_id,
            approved=allowed,
            action=RiskAction.APPROVE if allowed else RiskAction.REJECT,
            reason="; ".join(reasons),
            metadata={
                "rule_results": [
                    {
                        "code": result.code,
                        "allowed": result.allowed,
                        "reason": result.reason,
                    }
                    for result in rule_results
                ],
                "reasons": list(reasons),
            },
        )
        return RiskEvaluation(
            allowed=allowed,
            reasons=reasons,
            rule_results=rule_results,
            decision=decision,
        )


def check_max_daily_realized_loss(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    allowed = snapshot.realized_pnl_today > -config.max_daily_realized_loss
    return RuleResult(
        code="max_daily_realized_loss",
        allowed=allowed,
        reason="daily realized loss limit ok" if allowed else "max daily realized loss reached",
    )


def check_max_total_drawdown(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    drawdown = snapshot.peak_equity - snapshot.current_equity
    allowed = drawdown <= config.max_total_drawdown
    return RuleResult(
        code="max_total_drawdown",
        allowed=allowed,
        reason="total drawdown limit ok" if allowed else "max total drawdown reached",
    )


def check_max_trades_per_day(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    allowed = snapshot.trades_today < config.max_trades_per_day
    return RuleResult(
        code="max_trades_per_day",
        allowed=allowed,
        reason="daily trade count ok" if allowed else "max trades per day reached",
    )


def check_max_spread(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    allowed = snapshot.spread <= config.max_spread
    return RuleResult(
        code="max_spread",
        allowed=allowed,
        reason="spread threshold ok" if allowed else "spread threshold exceeded",
    )


def check_blocked_session(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    session = snapshot.session.lower()
    allowed = session not in config.blocked_sessions
    return RuleResult(
        code="blocked_session",
        allowed=allowed,
        reason="session allowed" if allowed else f"session blocked: {session}",
    )


def check_duplicate_signal(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del config
    allowed = signal.signal_id not in snapshot.seen_signal_ids
    return RuleResult(
        code="duplicate_signal",
        allowed=allowed,
        reason="signal is new" if allowed else "duplicate signal suppressed",
    )


def check_max_consecutive_losses(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    allowed = snapshot.consecutive_losses < config.max_consecutive_losses
    return RuleResult(
        code="max_consecutive_losses",
        allowed=allowed,
        reason="consecutive losses ok" if allowed else "max consecutive losses cooldown active",
    )


def check_mandatory_stop_loss(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del snapshot
    has_stop_loss = signal.features.get("stop_loss") is not None
    allowed = not config.require_stop_loss or signal.side == Side.FLAT or has_stop_loss
    return RuleResult(
        code="mandatory_stop_loss",
        allowed=allowed,
        reason="mandatory stop loss ok" if allowed else "stop loss required",
    )


def check_max_concurrent_positions(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    allowed = signal.side == Side.FLAT or snapshot.open_positions < config.max_concurrent_positions
    return RuleResult(
        code="max_concurrent_positions",
        allowed=allowed,
        reason="concurrent position limit ok" if allowed else "max concurrent positions reached",
    )


def check_news_blackout(
    signal: SignalEvent,
    snapshot: RiskSnapshot,
    config: RiskConfig,
) -> RuleResult:
    del signal
    active_windows = tuple(
        window.label
        for window in config.news_blackout_windows
        if window.contains(snapshot.timestamp)
    )
    allowed = not active_windows
    reason = "news blackout ok" if allowed else f"news blackout active: {', '.join(active_windows)}"
    return RuleResult(
        code="news_blackout",
        allowed=allowed,
        reason=reason,
    )


def build_snapshot_from_signal(
    signal: SignalEvent,
    *,
    realized_pnl_today: Decimal,
    current_equity: Decimal,
    peak_equity: Decimal,
    trades_today: int,
    spread: Decimal,
    session: str,
    seen_signal_ids: frozenset[str] = frozenset(),
    consecutive_losses: int = 0,
    open_positions: int = 0,
) -> RiskSnapshot:
    """Build a snapshot using the signal timestamp for deterministic evaluation."""

    return RiskSnapshot(
        timestamp=signal.timestamp,
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
