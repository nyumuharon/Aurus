"""CSV-backed OHLCV bar loading."""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurus.common.schemas import BarEvent, SourceMetadata
from aurus.data.quality import find_missing_bars, reject_duplicate_timestamps
from aurus.data.repository import BarRepository
from aurus.data.sessions import normalize_to_utc, tag_session

LOGGER = logging.getLogger(__name__)
REQUIRED_COLUMNS = frozenset({"timestamp", "open", "high", "low", "close", "volume"})


class CsvBarLoader(BarRepository):
    """Load OHLCV bars from a CSV file.

    Expected columns: timestamp, open, high, low, close, volume.
    Optional columns: spread, instrument, timeframe, correlation_id.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        default_instrument: str = "XAU/USD",
        default_timeframe: str = "1m",
        source_name: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.default_instrument = default_instrument
        self.default_timeframe = default_timeframe
        self.source = SourceMetadata(
            name=source_name or self.path.name,
            kind="csv_bar_loader",
        )

    def load_bars(
        self,
        *,
        instrument: str | None = None,
        timeframe: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[BarEvent]:
        selected_instrument = instrument or self.default_instrument
        selected_timeframe = timeframe or self.default_timeframe
        start_utc = normalize_to_utc(start) if start is not None else None
        end_utc = normalize_to_utc(end) if end is not None else None

        bars = list(self._read_bars())
        filtered = [
            bar
            for bar in bars
            if bar.instrument == selected_instrument
            and bar.timeframe == selected_timeframe
            and (start_utc is None or bar.timestamp >= start_utc)
            and (end_utc is None or bar.timestamp < end_utc)
        ]
        filtered.sort(key=lambda bar: bar.timestamp)
        reject_duplicate_timestamps(filtered)
        return filtered

    def load_and_check(
        self,
        *,
        expected_interval: timedelta,
        instrument: str | None = None,
        timeframe: str | None = None,
    ) -> list[BarEvent]:
        """Load bars and emit structured logs for missing bars."""

        bars = self.load_bars(instrument=instrument, timeframe=timeframe)
        find_missing_bars(bars, expected_interval)
        return bars

    def _read_bars(self) -> Iterable[BarEvent]:
        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or ())
            missing_columns = REQUIRED_COLUMNS - fieldnames
            if missing_columns:
                raise ValueError(f"CSV missing required columns: {sorted(missing_columns)}")

            for row_number, row in enumerate(reader, start=2):
                yield self._parse_row(row, row_number)

    def _parse_row(self, row: dict[str, str], row_number: int) -> BarEvent:
        timestamp = parse_timestamp(row["timestamp"])
        instrument = row.get("instrument") or self.default_instrument
        timeframe = row.get("timeframe") or self.default_timeframe
        correlation_id = row.get("correlation_id") or f"{self.path.name}:{row_number}"
        spread = parse_optional_decimal(row.get("spread"))

        bar = BarEvent(
            timestamp=timestamp,
            correlation_id=correlation_id,
            source=self.source,
            instrument=instrument,
            timeframe=timeframe,
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=Decimal(row["volume"]),
            spread=spread,
            metadata={
                "row_number": row_number,
                "session": tag_session(timestamp).value,
            },
        )
        LOGGER.debug(
            "loaded csv bar",
            extra={
                "event": "data.csv_bar_loaded",
                "path": str(self.path),
                "row_number": row_number,
                "timestamp": bar.timestamp.isoformat(),
                "instrument": bar.instrument,
                "timeframe": bar.timeframe,
            },
        )
        return bar


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and normalize it to UTC."""

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    return normalize_to_utc(datetime.fromisoformat(normalized))


def parse_optional_decimal(value: str | None) -> Decimal | None:
    """Parse an optional decimal CSV field."""

    if value is None or value.strip() == "":
        return None
    return Decimal(value)

