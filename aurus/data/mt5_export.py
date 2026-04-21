"""MetaTrader 5 historical data export helpers."""

from __future__ import annotations

import argparse
import csv
import importlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, cast


class MetaTrader5Module(Protocol):
    """Subset of the MetaTrader5 Python API used by the exporter."""

    TIMEFRAME_M5: int

    def initialize(self, *args: object, **kwargs: object) -> bool: ...

    def shutdown(self) -> None: ...

    def last_error(self) -> object: ...

    def symbol_select(self, symbol: str, enable: bool) -> bool: ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> object: ...


@dataclass(frozen=True)
class Mt5ExportConfig:
    """Configuration for exporting M5 historical bars from MetaTrader 5."""

    symbol: str
    output_path: Path
    start: datetime
    end: datetime
    terminal_path: Path | None = None
    login: int | None = None
    password: str | None = None
    server: str | None = None


@dataclass(frozen=True)
class Mt5ExportReport:
    """Summary of a deterministic M5 CSV export."""

    symbol: str
    output_path: Path
    rows_written: int
    start: datetime
    end: datetime


def export_mt5_m5_csv(
    config: Mt5ExportConfig,
    *,
    mt5_module: MetaTrader5Module | None = None,
) -> Mt5ExportReport:
    """Connect to a running MT5 terminal and export M5 OHLCV bars as CSV."""

    mt5 = mt5_module or import_metatrader5()
    initialize_kwargs: dict[str, object] = {}
    if config.terminal_path is not None:
        initialize_kwargs["path"] = str(config.terminal_path)
    if config.login is not None:
        initialize_kwargs["login"] = config.login
    if config.password is not None:
        initialize_kwargs["password"] = config.password
    if config.server is not None:
        initialize_kwargs["server"] = config.server

    initialized = mt5.initialize(**initialize_kwargs)
    if not initialized:
        raise RuntimeError(f"failed to initialize MetaTrader5: {mt5.last_error()}")

    try:
        if not mt5.symbol_select(config.symbol, True):
            raise RuntimeError(f"failed to select MT5 symbol {config.symbol}: {mt5.last_error()}")

        rates = mt5.copy_rates_range(
            config.symbol,
            mt5.TIMEFRAME_M5,
            require_utc(config.start, name="start"),
            require_utc(config.end, name="end"),
        )
        rows = sorted(mt5_rates_to_rows(rates), key=lambda row: row["timestamp"])
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
        with config.output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("timestamp", "open", "high", "low", "close", "volume", "spread"),
            )
            writer.writeheader()
            writer.writerows(rows)
        return Mt5ExportReport(
            symbol=config.symbol,
            output_path=config.output_path,
            rows_written=len(rows),
            start=config.start,
            end=config.end,
        )
    finally:
        mt5.shutdown()


def import_metatrader5() -> MetaTrader5Module:
    """Import the optional MetaTrader5 package with a clear installation error."""

    try:
        module = importlib.import_module("MetaTrader5")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MetaTrader5 Python package is not installed. Install it on the machine "
            "where the MetaTrader terminal is available, then rerun this exporter."
        ) from exc
    return cast(MetaTrader5Module, module)


def mt5_rates_to_rows(rates: object) -> list[dict[str, str]]:
    """Convert MT5 rate records into the canonical real 5M CSV format."""

    if rates is None:
        return []

    rows: list[dict[str, str]] = []
    seen_timestamps: set[str] = set()
    for rate in cast(Iterable[Any], rates):
        timestamp = datetime.fromtimestamp(int(rate["time"]), UTC).isoformat()
        if timestamp in seen_timestamps:
            continue
        seen_timestamps.add(timestamp)
        rows.append(
            {
                "timestamp": timestamp,
                "open": str(Decimal(str(rate["open"]))),
                "high": str(Decimal(str(rate["high"]))),
                "low": str(Decimal(str(rate["low"]))),
                "close": str(Decimal(str(rate["close"]))),
                "volume": str(Decimal(str(rate["tick_volume"]))),
                "spread": str(Decimal(str(rate["spread"]))),
            }
        )
    return rows


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO datetime and normalize it to UTC."""

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    return require_utc(parsed, name="datetime")


def require_utc(value: datetime, *, name: str) -> datetime:
    """Require a timezone-aware datetime and normalize it to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Export XAU/USD M5 bars from MetaTrader 5.")
    parser.add_argument("--symbol", default="XAUUSD", help="MT5 symbol name, e.g. XAUUSD.")
    parser.add_argument("--start", required=True, help="UTC ISO start time, inclusive.")
    parser.add_argument("--end", required=True, help="UTC ISO end time, exclusive.")
    parser.add_argument(
        "--output",
        default=Path("data/xauusd_m5.csv"),
        type=Path,
        help="Output CSV path.",
    )
    parser.add_argument("--terminal-path", default=None, type=Path, help="Optional terminal path.")
    parser.add_argument("--login", default=None, type=int, help="Optional MT5 account login.")
    parser.add_argument("--password", default=None, help="Optional MT5 account password.")
    parser.add_argument("--server", default=None, help="Optional MT5 broker server.")
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""

    args = parse_args()
    try:
        report = export_mt5_m5_csv(
            Mt5ExportConfig(
                symbol=args.symbol,
                output_path=args.output,
                start=parse_utc_datetime(args.start),
                end=parse_utc_datetime(args.end),
                terminal_path=args.terminal_path,
                login=args.login,
                password=args.password,
                server=args.server,
            )
        )
    except RuntimeError as exc:
        print(f"MT5 export failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"exported {report.rows_written} M5 bars for {report.symbol} to {report.output_path}")


if __name__ == "__main__":
    main()
