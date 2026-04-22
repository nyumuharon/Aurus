"""Execution package for broker adapters and order workflows."""

from aurus.execution.interfaces import ExecutionAdapter, ExecutionRepository
from aurus.execution.paper import (
    PaperExecutionAdapter,
    PaperExecutionConfig,
    calculate_average_price,
    normalize_order_intent,
    quantize_increment,
)
from aurus.execution.placeholder import COMPONENT
from aurus.execution.repository import InMemoryExecutionRepository, JsonlExecutionRepository

__all__ = [
    "COMPONENT",
    "ExecutionAdapter",
    "ExecutionRepository",
    "InMemoryExecutionRepository",
    "JsonlExecutionRepository",
    "PaperExecutionAdapter",
    "PaperExecutionConfig",
    "calculate_average_price",
    "normalize_order_intent",
    "quantize_increment",
]
