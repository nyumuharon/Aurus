"""Minimal deterministic risk implementations for backtests."""

from __future__ import annotations

from aurus.common.schemas import BarEvent, RiskAction, RiskDecision, SignalEvent, SourceMetadata


class ApproveAllRiskEngine:
    """Approve every signal.

    This is a test/backtest utility, not a production risk model.
    """

    def evaluate(self, signal: SignalEvent, bar: BarEvent) -> RiskDecision:
        return RiskDecision(
            timestamp=bar.timestamp,
            correlation_id=signal.correlation_id,
            source=SourceMetadata(name="approve-all-risk", kind="backtest_risk"),
            decision_id=f"risk-{signal.signal_id}",
            signal_id=signal.signal_id,
            approved=True,
            action=RiskAction.APPROVE,
            reason="approved by deterministic backtest risk adapter",
        )

