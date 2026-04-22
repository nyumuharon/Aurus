"""Tests for the deterministic event-driven backtest engine."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurus.backtest import BacktestConfig, BacktestEngine
from aurus.common.schemas import BarEvent, EventKind, Side, SignalEvent, domain_from_json
from pydantic import JsonValue


def bar(index: int, *, close: str, high: str | None = None, low: str | None = None) -> BarEvent:
    close_decimal = Decimal(close)
    return BarEvent(
        timestamp=datetime(2026, 4, 20, 7, 0, tzinfo=UTC) + timedelta(minutes=index),
        correlation_id=f"bar-{index}",
        instrument="XAU/USD",
        timeframe="1m",
        open=close_decimal,
        high=Decimal(high) if high is not None else close_decimal,
        low=Decimal(low) if low is not None else close_decimal,
        close=close_decimal,
        volume=Decimal("1"),
    )


def buy_signal(source_bar: BarEvent, **features: JsonValue) -> SignalEvent:
    return SignalEvent(
        timestamp=source_bar.timestamp,
        correlation_id=f"signal-{source_bar.correlation_id}",
        signal_id=f"signal-{source_bar.correlation_id}",
        strategy_id="test-strategy",
        instrument=source_bar.instrument,
        side=Side.BUY,
        strength=Decimal("1"),
        features=dict(features),
    )


def test_replays_bars_in_time_order() -> None:
    seen: list[datetime] = []

    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        seen.append(bars[-1].timestamp)
        return []

    unordered = [
        bar(2, close="100"),
        bar(0, close="100"),
        bar(1, close="100"),
    ]

    BacktestEngine(strategy=strategy).run(unordered)

    assert seen == sorted(seen)


def test_stop_loss_hit_closes_trade() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1", stop_loss="95", take_profit="110")]
        return []

    result = BacktestEngine(strategy=strategy).run(
        [
            bar(0, close="100"),
            bar(1, close="99", high="101", low="94"),
        ]
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].exit_price == Decimal("95")
    assert result.trades[0].net_pnl == Decimal("-5")


def test_take_profit_hit_closes_trade() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1", stop_loss="95", take_profit="105")]
        return []

    result = BacktestEngine(strategy=strategy).run(
        [
            bar(0, close="100"),
            bar(1, close="104", high="106", low="99"),
        ]
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "take_profit"
    assert result.trades[0].exit_price == Decimal("105")
    assert result.trades[0].net_pnl == Decimal("5")


def test_stop_tightening_moves_to_breakeven_after_half_r() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1", stop_loss="95", take_profit="120")]
        return []

    result = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(stop_tightening_enabled=True),
    ).run(
        [
            bar(0, close="100"),
            bar(1, close="102", high="102.5", low="100.5"),
            bar(2, close="100", high="101", low="99.5"),
        ]
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].exit_price == Decimal("100")
    assert result.trades[0].net_pnl == Decimal("0")


def test_stop_tightening_can_lock_profit_after_breakeven_trigger() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1", stop_loss="95", take_profit="120")]
        return []

    result = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(
            stop_tightening_enabled=True,
            breakeven_trigger_r=Decimal("0.5"),
            breakeven_stop_r=Decimal("0.1"),
        ),
    ).run(
        [
            bar(0, close="100"),
            bar(1, close="102", high="102.5", low="100.5"),
            bar(2, close="100", high="101", low="99.5"),
        ]
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].exit_price == Decimal("100.5")
    assert result.trades[0].net_pnl == Decimal("0.5")


def test_stop_tightening_trails_to_quarter_r_after_one_r() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1", stop_loss="95", take_profit="120")]
        return []

    result = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(stop_tightening_enabled=True),
    ).run(
        [
            bar(0, close="100"),
            bar(1, close="105", high="105", low="100.5"),
            bar(2, close="101", high="102", low="101"),
        ]
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].exit_price == Decimal("101.25")
    assert result.trades[0].net_pnl == Decimal("1.25")


def test_spread_and_slippage_reduce_realized_pnl() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1")]
        if len(bars) == 2:
            current = bars[-1]
            return [
                SignalEvent(
                    timestamp=current.timestamp,
                    correlation_id="exit",
                    signal_id="exit",
                    strategy_id="test-strategy",
                    instrument=current.instrument,
                    side=Side.FLAT,
                    strength=Decimal("1"),
                )
            ]
        return []

    no_cost_result = BacktestEngine(strategy=strategy).run(
        [bar(0, close="100"), bar(1, close="101")]
    )
    cost_result = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(spread=Decimal("0.20"), slippage=Decimal("0.05")),
    ).run([bar(0, close="100"), bar(1, close="101")])

    assert no_cost_result.trades[0].net_pnl == Decimal("1")
    assert cost_result.trades[0].entry_price == Decimal("100.15")
    assert cost_result.trades[0].exit_price == Decimal("100.85")
    assert cost_result.trades[0].net_pnl == Decimal("0.70")


def test_entry_exit_slippage_and_spread_multiplier_are_separate_execution_costs() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1")]
        if len(bars) == 2:
            current = bars[-1]
            return [
                SignalEvent(
                    timestamp=current.timestamp,
                    correlation_id="exit",
                    signal_id="exit",
                    strategy_id="test-strategy",
                    instrument=current.instrument,
                    side=Side.FLAT,
                    strength=Decimal("1"),
                )
            ]
        return []

    result = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(
            spread=Decimal("0.20"),
            spread_multiplier=Decimal("2"),
            entry_slippage=Decimal("0.03"),
            exit_slippage=Decimal("0.07"),
        ),
    ).run([bar(0, close="100"), bar(1, close="101")])

    assert result.trades[0].entry_price == Decimal("100.23")
    assert result.trades[0].exit_price == Decimal("100.73")
    assert result.trades[0].net_pnl == Decimal("0.50")


def test_event_log_is_deterministic_and_replayable() -> None:
    def strategy(bars: Sequence[BarEvent]) -> list[SignalEvent]:
        if len(bars) == 1:
            return [buy_signal(bars[-1], quantity="1", stop_loss="95", take_profit="105")]
        return []

    bars = [bar(0, close="100"), bar(1, close="104", high="106", low="99")]
    first = BacktestEngine(strategy=strategy).run(bars)
    second = BacktestEngine(strategy=strategy).run(bars)

    assert first.event_log == second.event_log
    replayed = tuple(domain_from_json(payload) for payload in first.event_log)
    assert replayed == first.events
    assert [event.event_kind for event in replayed[:3]] == [
        EventKind.BAR,
        EventKind.SIGNAL,
        EventKind.RISK_DECISION,
    ]
