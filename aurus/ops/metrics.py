"""Operational performance metrics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aurus.backtest.types import EquityPoint, TradeRecord


@dataclass(frozen=True)
class PerformanceMetrics:
    """Summary metrics for a run or trade sample."""

    total_pnl: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    profit_factor: Decimal | None
    trade_count: int
    winning_trades: int
    losing_trades: int


def total_pnl(trades: tuple[TradeRecord, ...]) -> Decimal:
    """Sum net PnL."""

    return sum((trade.net_pnl for trade in trades), Decimal("0"))


def max_drawdown(equity_curve: tuple[EquityPoint, ...]) -> Decimal:
    """Calculate peak-to-trough max drawdown from an equity curve."""

    if not equity_curve:
        return Decimal("0")
    peak = equity_curve[0].equity
    drawdown = Decimal("0")
    for point in equity_curve:
        if point.equity > peak:
            peak = point.equity
        current_drawdown = peak - point.equity
        if current_drawdown > drawdown:
            drawdown = current_drawdown
    return drawdown


def win_rate(trades: tuple[TradeRecord, ...]) -> Decimal:
    """Calculate winning-trade ratio."""

    if not trades:
        return Decimal("0")
    winners = sum(1 for trade in trades if trade.net_pnl > Decimal("0"))
    return Decimal(winners) / Decimal(len(trades))


def profit_factor(trades: tuple[TradeRecord, ...]) -> Decimal | None:
    """Calculate gross profit divided by gross loss.

    Returns None when there are no losing trades.
    """

    gross_profit = sum(
        (trade.net_pnl for trade in trades if trade.net_pnl > Decimal("0")),
        Decimal("0"),
    )
    gross_loss = abs(
        sum((trade.net_pnl for trade in trades if trade.net_pnl < Decimal("0")), Decimal("0"))
    )
    if gross_loss == Decimal("0"):
        return None
    return gross_profit / gross_loss


def calculate_metrics(
    trades: tuple[TradeRecord, ...],
    equity_curve: tuple[EquityPoint, ...],
) -> PerformanceMetrics:
    """Calculate standard operational performance metrics."""

    winning_trades = sum(1 for trade in trades if trade.net_pnl > Decimal("0"))
    losing_trades = sum(1 for trade in trades if trade.net_pnl < Decimal("0"))
    return PerformanceMetrics(
        total_pnl=total_pnl(trades),
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate(trades),
        profit_factor=profit_factor(trades),
        trade_count=len(trades),
        winning_trades=winning_trades,
        losing_trades=losing_trades,
    )

