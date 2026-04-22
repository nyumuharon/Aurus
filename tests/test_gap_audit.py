"""Tests for the real-data gap audit command helpers."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from aurus.backtest.audit_real_gaps import (
    format_gap_audit_summary,
    gap_audit_row,
    write_gap_audit_csv,
)
from aurus.data.quality import MissingBarGap

NOW = datetime(2026, 4, 20, 7, 0, tzinfo=UTC)


def gap() -> MissingBarGap:
    return MissingBarGap(
        previous_timestamp=NOW,
        next_timestamp=NOW + timedelta(minutes=15),
        missing_timestamps=(
            NOW + timedelta(minutes=5),
            NOW + timedelta(minutes=10),
        ),
    )


def test_gap_audit_row_marks_active_gap() -> None:
    row = gap_audit_row(
        gap(),
        active_gap_ids={(NOW.isoformat(), (NOW + timedelta(minutes=15)).isoformat())},
    )

    assert row["missing_bars"] == "2"
    assert row["first_missing_timestamp"] == (NOW + timedelta(minutes=5)).isoformat()
    assert row["active_strategy_window"] == "True"


def test_write_gap_audit_csv(tmp_path: Path) -> None:
    output = tmp_path / "gaps.csv"

    write_gap_audit_csv(path=output, gaps=(gap(),), active_gaps=(gap(),))

    contents = output.read_text(encoding="utf-8")
    assert "previous_timestamp,next_timestamp,missing_bars" in contents
    assert "True" in contents


def test_format_gap_audit_summary() -> None:
    summary = format_gap_audit_summary(
        gaps=(gap(),),
        active_gaps=(gap(),),
        output=Path("artifacts/gaps.csv"),
    )

    assert "total gaps: 1" in summary
    assert "active strategy missing bars: 2" in summary
    assert "active unexpected gaps: 1" in summary
