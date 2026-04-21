"""Tests for MetaTrader 5 M5 CSV export."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from aurus.data.mt5_export import (
    Mt5ExportConfig,
    export_mt5_m5_csv,
    mt5_rates_to_rows,
    parse_utc_datetime,
)


class FakeMt5:
    TIMEFRAME_M5 = 5

    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_called = False
        self.selected_symbol: str | None = None

    def initialize(self, *args: object, **kwargs: object) -> bool:
        self.initialized = True
        return True

    def shutdown(self) -> None:
        self.shutdown_called = True

    def last_error(self) -> object:
        return (0, "ok")

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        self.selected_symbol = symbol if enable else None
        return enable

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> object:
        return [
            {
                "time": int(datetime(2026, 1, 5, 0, 5, tzinfo=UTC).timestamp()),
                "open": 2401.0,
                "high": 2402.0,
                "low": 2400.0,
                "close": 2401.5,
                "tick_volume": 11,
                "spread": 25,
            },
            {
                "time": int(datetime(2026, 1, 5, 0, 0, tzinfo=UTC).timestamp()),
                "open": 2400.0,
                "high": 2401.0,
                "low": 2399.0,
                "close": 2400.5,
                "tick_volume": 10,
                "spread": 20,
            },
        ]


def test_mt5_rates_to_rows_outputs_canonical_csv_rows() -> None:
    rows = mt5_rates_to_rows(
        [
            {
                "time": int(datetime(2026, 1, 5, 0, 0, tzinfo=UTC).timestamp()),
                "open": 2400.0,
                "high": 2401.0,
                "low": 2399.0,
                "close": 2400.5,
                "tick_volume": 10,
                "spread": 20,
            }
        ]
    )

    assert rows == [
        {
            "timestamp": "2026-01-05T00:00:00+00:00",
            "open": "2400.0",
            "high": "2401.0",
            "low": "2399.0",
            "close": "2400.5",
            "volume": "10",
            "spread": "20",
        }
    ]


def test_export_mt5_m5_csv_writes_sorted_csv(tmp_path: Path) -> None:
    output_path = tmp_path / "xauusd_m5.csv"
    fake_mt5 = FakeMt5()

    report = export_mt5_m5_csv(
        Mt5ExportConfig(
            symbol="XAUUSD",
            output_path=output_path,
            start=datetime(2026, 1, 5, 0, 0, tzinfo=UTC),
            end=datetime(2026, 1, 5, 1, 0, tzinfo=UTC),
        ),
        mt5_module=fake_mt5,
    )

    assert report.rows_written == 2
    assert fake_mt5.initialized
    assert fake_mt5.shutdown_called
    assert fake_mt5.selected_symbol == "XAUUSD"
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        "timestamp,open,high,low,close,volume,spread",
        "2026-01-05T00:00:00+00:00,2400.0,2401.0,2399.0,2400.5,10,20",
        "2026-01-05T00:05:00+00:00,2401.0,2402.0,2400.0,2401.5,11,25",
    ]


def test_parse_utc_datetime_requires_timezone() -> None:
    assert parse_utc_datetime("2026-01-05T03:00:00+03:00") == datetime(
        2026, 1, 5, 0, 0, tzinfo=UTC
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_utc_datetime("2026-01-05T00:00:00")
