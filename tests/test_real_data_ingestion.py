"""Tests for real XAU/USD CSV ingestion and backtest integration."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from aurus.backtest.run_real_baseline import (
    current_best_real_backtest_config,
    current_best_real_config,
    format_ingestion_report,
    format_real_baseline_summary,
    run_real_baseline_backtest,
)
from aurus.data import TradingSession, load_real_xauusd_5m_csv


def test_current_best_real_config_uses_profitable_reference_branch() -> None:
    strategy_config = current_best_real_config()
    backtest_config = current_best_real_backtest_config()

    assert strategy_config.reward_risk == Decimal("1.10")
    assert strategy_config.execution_ema_period == 5
    assert strategy_config.min_atr_strength == Decimal("0.0005")
    assert strategy_config.min_trend_strength == Decimal("0.0002")
    assert strategy_config.min_pre_entry_extension_atr == Decimal("0.645")
    assert strategy_config.allowed_sessions == frozenset({TradingSession.LONDON.value})
    assert strategy_config.allowed_london_subwindows == frozenset({"open", "mid"})
    assert backtest_config.stop_tightening_enabled is True
    assert backtest_config.breakeven_trigger_r == Decimal("0.25")
    assert backtest_config.breakeven_stop_r == Decimal("0.20")
    assert backtest_config.trailing_trigger_r == Decimal("0.75")
    assert backtest_config.trailing_stop_r == Decimal("0.50")


def test_real_csv_ingestion_sorts_deduplicates_and_reports_missing_bars(tmp_path: Path) -> None:
    csv_path = tmp_path / "real_xauusd_5m.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume,spread",
                "2026-01-05T00:10:00Z,100,101,99,100.5,10,0.20",
                "2026-01-05T00:00:00Z,99,100,98,99.5,11,0.20",
                "2026-01-05T00:00:00Z,999,999,999,999,99,0.99",
            ]
        ),
        encoding="utf-8",
    )

    data = load_real_xauusd_5m_csv(csv_path)

    assert [bar.timestamp for bar in data.execution_bars] == [
        datetime(2026, 1, 5, 0, 0, tzinfo=UTC),
        datetime(2026, 1, 5, 0, 10, tzinfo=UTC),
    ]
    assert data.execution_bars[0].open == Decimal("99")
    assert data.report.input_rows == 3
    assert data.report.output_bars == 2
    assert data.report.duplicates_removed == 1
    assert data.report.missing_bar_count == 1
    assert data.report.missing_gaps[0].missing_timestamps == (
        datetime(2026, 1, 5, 0, 5, tzinfo=UTC),
    )


def test_real_csv_ingestion_supports_optional_spread_fallback(tmp_path: Path) -> None:
    csv_path = tmp_path / "real_xauusd_5m.csv"
    rows = ["timestamp,open,high,low,close,volume"]
    for index in range(12):
        rows.append(
            f"2026-01-05T00:{index * 5:02d}:00Z,"
            f"{100 + index},{101 + index},{99 + index},{100 + index},10"
        )
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    data = load_real_xauusd_5m_csv(csv_path, fallback_spread=Decimal("0.25"))

    assert len(data.execution_bars) == 12
    assert data.execution_bars[0].spread == Decimal("0.25")
    assert len(data.context_bars) == 1
    assert data.context_bars[0].timestamp == datetime(2026, 1, 5, 1, 0, tzinfo=UTC)
    assert data.context_bars[0].open == Decimal("100")
    assert data.context_bars[0].close == Decimal("111")
    assert data.context_bars[0].spread == Decimal("0.25")


def test_real_csv_ingestion_normalizes_mt5_integer_spread_points(tmp_path: Path) -> None:
    csv_path = tmp_path / "real_xauusd_5m.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume,spread",
                "2026-01-05T00:00:00Z,100,101,99,100.5,10,25",
                "2026-01-05T00:05:00Z,100,101,99,100.5,10,33",
                "2026-01-05T00:10:00Z,100,101,99,100.5,10,100",
                "2026-01-05T00:15:00Z,100,101,99,100.5,10,0.20",
                "2026-01-05T00:20:00Z,100,101,99,100.5,10,1.00",
            ]
        ),
        encoding="utf-8",
    )

    data = load_real_xauusd_5m_csv(csv_path)

    assert [bar.spread for bar in data.execution_bars] == [
        Decimal("0.25"),
        Decimal("0.33"),
        Decimal("1.00"),
        Decimal("0.20"),
        Decimal("1.00"),
    ]


def test_real_baseline_runner_integrates_with_backtest_engine(tmp_path: Path) -> None:
    csv_path = tmp_path / "real_xauusd_5m.csv"
    rows = ["timestamp,open,high,low,close,volume,spread"]
    for index in range(48):
        rows.append(
            f"2026-01-05T{index // 12:02d}:{(index % 12) * 5:02d}:00Z,"
            f"{100 + index},{101 + index},{99 + index},{100 + index},10,0.20"
        )
    csv_path.write_text("\n".join(rows), encoding="utf-8")
    data = load_real_xauusd_5m_csv(csv_path)

    result = run_real_baseline_backtest(data=data)

    assert len(result.equity_curve) == 48
    assert "Real CSV ingestion report" in format_ingestion_report(data)
    assert "total trades:" in format_real_baseline_summary(result)
