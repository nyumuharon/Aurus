"""Strategy package reserved for falsifiable strategy hypotheses."""

from aurus.strategy.baseline import (
    BaselineDiagnostics,
    BaselineStrategyConfig,
    BaselineXauUsdStrategy,
    ConfirmationMode,
    EntryMode,
    LondonSubwindow,
    StopTarget,
    calculate_stop_target,
)
from aurus.strategy.indicators import atr, ema, true_ranges
from aurus.strategy.placeholder import COMPONENT

__all__ = [
    "COMPONENT",
    "BaselineDiagnostics",
    "BaselineStrategyConfig",
    "BaselineXauUsdStrategy",
    "ConfirmationMode",
    "EntryMode",
    "LondonSubwindow",
    "StopTarget",
    "atr",
    "calculate_stop_target",
    "ema",
    "true_ranges",
]
