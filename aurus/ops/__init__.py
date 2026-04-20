"""Operations package for observability, audit, and recoverability tooling."""

from aurus.ops.journal import EventJournal
from aurus.ops.ledger import (
    CsvTradeLedgerRepository,
    InMemoryTradeLedgerRepository,
    TradeLedgerRepository,
)
from aurus.ops.logging import JsonLogFormatter, configure_structured_logging
from aurus.ops.metrics import (
    PerformanceMetrics,
    calculate_metrics,
    max_drawdown,
    profit_factor,
    total_pnl,
    win_rate,
)
from aurus.ops.placeholder import COMPONENT
from aurus.ops.summary import summarize_metrics, summarize_run

__all__ = [
    "COMPONENT",
    "CsvTradeLedgerRepository",
    "EventJournal",
    "InMemoryTradeLedgerRepository",
    "JsonLogFormatter",
    "PerformanceMetrics",
    "TradeLedgerRepository",
    "calculate_metrics",
    "configure_structured_logging",
    "max_drawdown",
    "profit_factor",
    "summarize_metrics",
    "summarize_run",
    "total_pnl",
    "win_rate",
]
