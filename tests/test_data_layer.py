"""Tests for historical market data loading and quality checks."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from aurus.common.schemas import BarEvent
from aurus.data import CsvBarLoader, TradingSession, find_missing_bars, tag_session


def make_bar(timestamp: datetime) -> BarEvent:
    return BarEvent(
        timestamp=timestamp,
        correlation_id=timestamp.isoformat(),
        timeframe="1m",
        open=Decimal("2380.0"),
        high=Decimal("2381.0"),
        low=Decimal("2379.5"),
        close=Decimal("2380.5"),
        volume=Decimal("10"),
    )


def test_csv_loader_normalizes_timestamps_to_utc(tmp_path) -> None:
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume,spread",
                "2026-04-20T09:30:00+03:00,2380.0,2381.0,2379.5,2380.5,10,0.20",
            ]
        ),
        encoding="utf-8",
    )

    bars = CsvBarLoader(csv_path).load_bars()

    assert bars[0].timestamp == datetime(2026, 4, 20, 6, 30, tzinfo=UTC)
    assert bars[0].spread == Decimal("0.20")
    assert bars[0].metadata["session"] == TradingSession.ASIA.value


def test_csv_loader_rejects_duplicate_timestamps_and_logs_issue(tmp_path, caplog) -> None:
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-04-20T07:00:00+00:00,2380.0,2381.0,2379.5,2380.5,10",
                "2026-04-20T07:00:00Z,2380.5,2381.5,2380.0,2381.0,11",
            ]
        ),
        encoding="utf-8",
    )

    with (
        caplog.at_level("WARNING", logger="aurus.data.quality"),
        pytest.raises(ValueError, match="duplicate bar timestamps"),
    ):
        CsvBarLoader(csv_path).load_bars()

    assert any(record.event == "data_quality.duplicate_timestamps" for record in caplog.records)


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (datetime(2026, 4, 20, 1, 0, tzinfo=UTC), TradingSession.ASIA),
        (datetime(2026, 4, 20, 8, 0, tzinfo=UTC), TradingSession.LONDON),
        (datetime(2026, 4, 20, 14, 0, tzinfo=UTC), TradingSession.NEW_YORK),
        (datetime(2026, 4, 20, 21, 30, tzinfo=UTC), TradingSession.ROLLOVER),
        (
            datetime(2026, 4, 20, 16, 0, tzinfo=timezone(timedelta(hours=3))),
            TradingSession.NEW_YORK,
        ),
    ],
)
def test_session_tagging_correctness(timestamp: datetime, expected: TradingSession) -> None:
    assert tag_session(timestamp) == expected


def test_missing_bar_detection_on_sample_data(caplog) -> None:
    bars = [
        make_bar(datetime(2026, 4, 20, 7, 0, tzinfo=UTC)),
        make_bar(datetime(2026, 4, 20, 7, 1, tzinfo=UTC)),
        make_bar(datetime(2026, 4, 20, 7, 4, tzinfo=UTC)),
    ]

    with caplog.at_level("WARNING", logger="aurus.data.quality"):
        gaps = find_missing_bars(bars, timedelta(minutes=1))

    assert len(gaps) == 1
    assert gaps[0].missing_timestamps == (
        datetime(2026, 4, 20, 7, 2, tzinfo=UTC),
        datetime(2026, 4, 20, 7, 3, tzinfo=UTC),
    )
    assert any(record.event == "data_quality.missing_bars" for record in caplog.records)
