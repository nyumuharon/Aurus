"""Deterministic event-driven backtesting engine."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from aurus.backtest.interfaces import RiskEngine, StrategyCallback
from aurus.backtest.risk import ApproveAllRiskEngine
from aurus.backtest.types import (
    BacktestConfig,
    BacktestResult,
    BacktestState,
    EquityPoint,
    OpenPosition,
    TradeRecord,
)
from aurus.common.schemas import (
    BarEvent,
    DomainModel,
    FillEvent,
    OrderEvent,
    OrderIntent,
    OrderStatus,
    OrderType,
    PositionSnapshot,
    RiskAction,
    Side,
    SignalEvent,
    SourceMetadata,
    TimeInForce,
)

BACKTEST_SOURCE = SourceMetadata(name="aurus-backtest", kind="backtest_engine")


class BacktestEngine:
    """Replay bars, route signals through risk, and simulate fills."""

    def __init__(
        self,
        *,
        strategy: StrategyCallback,
        risk_engine: RiskEngine | None = None,
        config: BacktestConfig | None = None,
    ) -> None:
        self.strategy = strategy
        self.risk_engine = risk_engine or ApproveAllRiskEngine()
        self.config = config or BacktestConfig()

    def run(self, bars: list[BarEvent]) -> BacktestResult:
        ordered_bars = sorted(bars, key=lambda bar: bar.timestamp)
        state = BacktestState(cash=self.config.initial_cash)

        for bar in ordered_bars:
            self._record_event(state, bar)
            self._check_protective_exit(state, bar)
            state.bars.append(bar)

            signals = self.strategy(tuple(state.bars))
            for signal in signals:
                self._record_event(state, signal)
                self._process_signal(state, bar, signal)

            self._mark_equity(state, bar)

        return self._build_result(state)

    def persist_event_log(self, result: BacktestResult, path: str | Path) -> None:
        """Persist deterministic replay events as JSON lines."""

        Path(path).write_text("\n".join(result.event_log) + "\n", encoding="utf-8")

    def _process_signal(self, state: BacktestState, bar: BarEvent, signal: SignalEvent) -> None:
        risk_decision = self.risk_engine.evaluate(signal, bar)
        self._record_event(state, risk_decision)
        if not risk_decision.approved or risk_decision.action == RiskAction.REJECT:
            return

        quantity = risk_decision.max_quantity or _decimal_feature(
            signal,
            "quantity",
            self.config.default_quantity,
        )
        if quantity is None or quantity <= Decimal("0"):
            return

        if signal.side == Side.FLAT:
            if state.position is not None:
                self._close_position(state, bar, "signal_exit")
            return

        if state.position is not None:
            if state.position.side == signal.side:
                return
            self._close_position(state, bar, "signal_reverse")

        self._open_position(state, bar, signal, quantity)

    def _open_position(
        self,
        state: BacktestState,
        bar: BarEvent,
        signal: SignalEvent,
        quantity: Decimal,
    ) -> None:
        fill_price = self._entry_price(bar, signal.side)
        intent_id = state.next_id("intent")
        order_id = state.next_id("order")
        fill_id = state.next_id("fill")

        intent = OrderIntent(
            timestamp=bar.timestamp,
            correlation_id=signal.correlation_id,
            source=BACKTEST_SOURCE,
            intent_id=intent_id,
            risk_decision_id=f"risk-{signal.signal_id}",
            instrument=signal.instrument,
            side=signal.side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            time_in_force=TimeInForce.IOC,
        )
        order = OrderEvent(
            timestamp=bar.timestamp,
            correlation_id=signal.correlation_id,
            source=BACKTEST_SOURCE,
            order_id=order_id,
            intent_id=intent_id,
            instrument=signal.instrument,
            side=signal.side,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            quantity=quantity,
            filled_quantity=quantity,
            average_fill_price=fill_price,
        )
        fill = FillEvent(
            timestamp=bar.timestamp,
            correlation_id=signal.correlation_id,
            source=BACKTEST_SOURCE,
            fill_id=fill_id,
            order_id=order_id,
            instrument=signal.instrument,
            side=signal.side,
            quantity=quantity,
            price=fill_price,
            commission=self.config.commission_per_fill,
        )

        for event in (intent, order, fill):
            self._record_event(state, event)

        state.position = OpenPosition(
            instrument=signal.instrument,
            side=signal.side,
            quantity=quantity,
            entry_timestamp=bar.timestamp,
            entry_price=fill_price,
            entry_fill_id=fill_id,
            stop_loss=_decimal_feature(signal, "stop_loss", None),
            take_profit=_decimal_feature(signal, "take_profit", None),
            commission=self.config.commission_per_fill,
        )

    def _check_protective_exit(self, state: BacktestState, bar: BarEvent) -> None:
        position = state.position
        if position is None:
            return

        if position.side == Side.BUY:
            if position.stop_loss is not None and bar.low <= position.stop_loss:
                self._close_position(state, bar, "stop_loss", position.stop_loss)
                return
            if position.take_profit is not None and bar.high >= position.take_profit:
                self._close_position(state, bar, "take_profit", position.take_profit)
                return

        if position.side == Side.SELL:
            if position.stop_loss is not None and bar.high >= position.stop_loss:
                self._close_position(state, bar, "stop_loss", position.stop_loss)
                return
            if position.take_profit is not None and bar.low <= position.take_profit:
                self._close_position(state, bar, "take_profit", position.take_profit)

    def _close_position(
        self,
        state: BacktestState,
        bar: BarEvent,
        reason: str,
        trigger_price: Decimal | None = None,
    ) -> None:
        position = state.position
        if position is None:
            return

        exit_side = Side.SELL if position.side == Side.BUY else Side.BUY
        exit_price = self._exit_price(bar, exit_side, trigger_price)
        order_id = state.next_id("order")
        fill_id = state.next_id("fill")
        correlation_id = f"{position.entry_fill_id}:{reason}"

        order = OrderEvent(
            timestamp=bar.timestamp,
            correlation_id=correlation_id,
            source=BACKTEST_SOURCE,
            order_id=order_id,
            broker_order_id=None,
            instrument=position.instrument,
            side=exit_side,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            quantity=position.quantity,
            filled_quantity=position.quantity,
            average_fill_price=exit_price,
            message=reason,
        )
        fill = FillEvent(
            timestamp=bar.timestamp,
            correlation_id=correlation_id,
            source=BACKTEST_SOURCE,
            fill_id=fill_id,
            order_id=order_id,
            instrument=position.instrument,
            side=exit_side,
            quantity=position.quantity,
            price=exit_price,
            commission=self.config.commission_per_fill,
            liquidity="simulated",
        )
        self._record_event(state, order)
        self._record_event(state, fill)

        gross_pnl = self._gross_pnl(position, exit_price)
        commission = position.commission + self.config.commission_per_fill
        net_pnl = gross_pnl - commission
        state.realized_pnl += net_pnl
        state.cash += net_pnl
        state.trades.append(
            TradeRecord(
                trade_id=position.entry_fill_id,
                instrument=position.instrument,
                side=position.side,
                quantity=position.quantity,
                entry_timestamp=position.entry_timestamp,
                exit_timestamp=bar.timestamp,
                entry_price=position.entry_price,
                exit_price=exit_price,
                gross_pnl=gross_pnl,
                commission=commission,
                net_pnl=net_pnl,
                exit_reason=reason,
            )
        )
        state.position = None

    def _entry_price(self, bar: BarEvent, side: Side) -> Decimal:
        half_spread = self._bar_spread(bar) / Decimal("2")
        if side == Side.BUY:
            return bar.close + half_spread + self.config.slippage
        if side == Side.SELL:
            return bar.close - half_spread - self.config.slippage
        raise ValueError("entry side cannot be flat")

    def _exit_price(
        self,
        bar: BarEvent,
        side: Side,
        trigger_price: Decimal | None = None,
    ) -> Decimal:
        base_price = trigger_price or bar.close
        half_spread = self._bar_spread(bar) / Decimal("2")
        if side == Side.BUY:
            return base_price + half_spread + self.config.slippage
        if side == Side.SELL:
            return base_price - half_spread - self.config.slippage
        raise ValueError("exit side cannot be flat")

    def _bar_spread(self, bar: BarEvent) -> Decimal:
        return bar.spread if bar.spread is not None else self.config.spread

    def _mark_equity(self, state: BacktestState, bar: BarEvent) -> None:
        unrealized = Decimal("0")
        quantity = Decimal("0")
        average_price: Decimal | None = None
        if state.position is not None:
            unrealized = self._gross_pnl(state.position, self._mark_price(state.position, bar))
            quantity = (
                state.position.quantity
                if state.position.side == Side.BUY
                else -state.position.quantity
            )
            average_price = state.position.entry_price

        equity = state.cash + unrealized
        state.equity_curve.append(
            EquityPoint(
                timestamp=bar.timestamp,
                cash=state.cash,
                realized_pnl=state.realized_pnl,
                unrealized_pnl=unrealized,
                equity=equity,
            )
        )
        self._record_event(
            state,
            PositionSnapshot(
                timestamp=bar.timestamp,
                correlation_id=f"position-{bar.correlation_id}",
                source=BACKTEST_SOURCE,
                account_id=self.config.account_id,
                instrument=bar.instrument,
                quantity=quantity,
                average_price=average_price,
                mark_price=bar.close,
                realized_pnl=state.realized_pnl,
                unrealized_pnl=unrealized,
            ),
        )

    def _mark_price(self, position: OpenPosition, bar: BarEvent) -> Decimal:
        exit_side = Side.SELL if position.side == Side.BUY else Side.BUY
        return self._exit_price(bar, exit_side)

    def _gross_pnl(self, position: OpenPosition, exit_price: Decimal) -> Decimal:
        if position.side == Side.BUY:
            return (exit_price - position.entry_price) * position.quantity
        return (position.entry_price - exit_price) * position.quantity

    def _record_event(self, state: BacktestState, event: DomainModel) -> None:
        state.events.append(event)

    def _build_result(self, state: BacktestState) -> BacktestResult:
        event_log = tuple(event.to_json() for event in state.events)
        return BacktestResult(
            trades=tuple(state.trades),
            equity_curve=tuple(state.equity_curve),
            event_log=event_log,
            events=tuple(state.events),
        )


def _decimal_feature(
    signal: SignalEvent,
    key: str,
    default: Decimal | None,
) -> Decimal | None:
    raw_value = signal.features.get(key)
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        raise ValueError(f"{key} cannot be a boolean")
    return Decimal(str(raw_value))
