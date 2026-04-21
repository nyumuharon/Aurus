"""Real historical XAU/USD 5-minute CSV ingestion."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurus.common.schemas import BarEvent, SourceMetadata
from aurus.data.csv_loader import parse_optional_decimal, parse_timestamp
from aurus.data.quality import MissingBarGap, find_missing_bars
from aurus.data.sessions import tag_session

LOGGER = logging.getLogger(__name__)
REAL_5M_CSV_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "spread")
REQUIRED_REAL_5M_COLUMNS = frozenset({"timestamp", "open", "high", "low", "close", "volume"})
FIVE_MINUTE_INTERVAL = timedelta(minutes=5)
XAUUSD_MT5_SPREAD_POINT_SIZE = Decimal("0.01")


@dataclass(frozen=True)
class RealCsvIngestionReport:
    """Deterministic data quality summary for an ingested real CSV."""

    source_path: Path
    input_rows: int
    output_bars: int
    duplicates_removed: int
    missing_gaps: tuple[MissingBarGap, ...]

    @property
    def missing_bar_count(self) -> int:
        """Total missing 5-minute timestamps across all detected gaps."""

        return sum(len(gap.missing_timestamps) for gap in self.missing_gaps)


@dataclass(frozen=True)
class IngestedMarketData:
    """Execution and context bars prepared for backtesting."""

    execution_bars: list[BarEvent]
    context_bars: list[BarEvent]
    report: RealCsvIngestionReport


def load_real_xauusd_5m_csv(
    path: str | Path,
    *,
    instrument: str = "XAU/USD",
    fallback_spread: Decimal | None = None,
) -> IngestedMarketData:
    """Load real 5-minute XAU/USD OHLCV CSV data for the baseline backtester.

    Expected CSV columns:
    timestamp, open, high, low, close, volume, spread

    The spread column is optional. If it is omitted or blank, fallback_spread is used when
    provided; otherwise the loaded bars keep spread=None.
    """

    source_path = Path(path)
    source = SourceMetadata(name=source_path.name, kind="real_5m_csv")
    raw_bars = _read_real_5m_bars(
        source_path,
        instrument=instrument,
        source=source,
        fallback_spread=fallback_spread,
    )
    deduplicated_bars, duplicates_removed = _deduplicate_by_timestamp(raw_bars)
    execution_bars = sorted(deduplicated_bars, key=lambda bar: bar.timestamp)
    missing_gaps = find_missing_bars(execution_bars, FIVE_MINUTE_INTERVAL)
    context_bars = aggregate_closed_hourly_bars(execution_bars, source=source)
    report = RealCsvIngestionReport(
        source_path=source_path,
        input_rows=len(raw_bars),
        output_bars=len(execution_bars),
        duplicates_removed=duplicates_removed,
        missing_gaps=missing_gaps,
    )
    return IngestedMarketData(
        execution_bars=execution_bars,
        context_bars=context_bars,
        report=report,
    )


def aggregate_closed_hourly_bars(
    bars: list[BarEvent],
    *,
    source: SourceMetadata | None = None,
) -> list[BarEvent]:
    """Aggregate continuous 5-minute bars into closed 1-hour context bars."""

    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    bars_by_hour: dict[datetime, list[BarEvent]] = {}
    for bar in ordered:
        hour_start = bar.timestamp.replace(minute=0, second=0, microsecond=0)
        bars_by_hour.setdefault(hour_start, []).append(bar)

    hourly_bars: list[BarEvent] = []
    for hour_start in sorted(bars_by_hour):
        window = sorted(bars_by_hour[hour_start], key=lambda bar: bar.timestamp)
        if len(window) != 12:
            LOGGER.warning(
                "skipping incomplete hourly aggregation window",
                extra={
                    "event": "data_quality.incomplete_hourly_aggregation_window",
                    "hour_start": hour_start.isoformat(),
                    "bar_count": len(window),
                },
            )
            continue
        if not _is_contiguous_window(window):
            LOGGER.warning(
                "skipping non-contiguous hourly aggregation window",
                extra={
                    "event": "data_quality.hourly_aggregation_gap",
                    "start_timestamp": window[0].timestamp.isoformat(),
                    "end_timestamp": window[-1].timestamp.isoformat(),
                },
            )
            continue

        close_timestamp = hour_start + timedelta(hours=1)
        spread_values = [bar.spread for bar in window if bar.spread is not None]
        average_spread = (
            sum(spread_values, Decimal("0")) / Decimal(len(spread_values))
            if spread_values
            else None
        )
        hourly_bars.append(
            BarEvent(
                timestamp=close_timestamp,
                correlation_id=f"1h:{close_timestamp.isoformat()}",
                source=source,
                instrument=window[0].instrument,
                timeframe="1h",
                open=window[0].open,
                high=max(bar.high for bar in window),
                low=min(bar.low for bar in window),
                close=window[-1].close,
                volume=sum((bar.volume for bar in window), Decimal("0")),
                spread=average_spread,
                metadata={
                    "source_timeframe": "5m",
                    "aggregation": "closed_1h",
                    "session": tag_session(close_timestamp).value,
                },
            )
        )
    return hourly_bars


def _read_real_5m_bars(
    path: Path,
    *,
    instrument: str,
    source: SourceMetadata,
    fallback_spread: Decimal | None,
) -> list[BarEvent]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing_columns = REQUIRED_REAL_5M_COLUMNS - fieldnames
        if missing_columns:
            raise ValueError(f"real 5m CSV missing required columns: {sorted(missing_columns)}")

        bars: list[BarEvent] = []
        for row_number, row in enumerate(reader, start=2):
            timestamp = parse_timestamp(row["timestamp"])
            parsed_spread = parse_optional_decimal(row.get("spread"))
            spread = (
                _normalize_xauusd_spread(row.get("spread"), parsed_spread)
                if parsed_spread is not None
                else fallback_spread
            )
            bars.append(
                BarEvent(
                    timestamp=timestamp,
                    correlation_id=f"{path.name}:{row_number}",
                    source=source,
                    instrument=instrument,
                    timeframe="5m",
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
            )
    return bars


def _normalize_xauusd_spread(raw_value: str | None, parsed_spread: Decimal) -> Decimal:
    stripped = raw_value.strip() if raw_value is not None else ""
    # MT5 exports XAU/USD spread as integer points. Aurus models spread in price units, so
    # 25 points becomes 0.25, 33 points becomes 0.33, and decimal values remain unchanged.
    if stripped.isdecimal():
        return parsed_spread * XAUUSD_MT5_SPREAD_POINT_SIZE
    return parsed_spread


def _deduplicate_by_timestamp(bars: list[BarEvent]) -> tuple[list[BarEvent], int]:
    by_timestamp: dict[datetime, BarEvent] = {}
    duplicates_removed = 0
    for bar in bars:
        if bar.timestamp in by_timestamp:
            duplicates_removed += 1
            continue
        by_timestamp[bar.timestamp] = bar

    if duplicates_removed:
        LOGGER.warning(
            "duplicate real 5m timestamps removed",
            extra={
                "event": "data_quality.duplicate_timestamps_removed",
                "duplicates_removed": duplicates_removed,
            },
        )
    return list(by_timestamp.values()), duplicates_removed


def _is_contiguous_window(window: list[BarEvent]) -> bool:
    for previous, current in zip(window, window[1:], strict=False):
        if current.timestamp - previous.timestamp != FIVE_MINUTE_INTERVAL:
            return False
    return True
