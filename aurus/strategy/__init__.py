"""Strategy package reserved for falsifiable strategy hypotheses."""

from aurus.strategy.baseline import (
    BaselineStrategyConfig,
    BaselineXauUsdStrategy,
    StopTarget,
    calculate_stop_target,
)
from aurus.strategy.indicators import atr, ema, true_ranges
from aurus.strategy.placeholder import COMPONENT

__all__ = [
    "COMPONENT",
    "BaselineStrategyConfig",
    "BaselineXauUsdStrategy",
    "StopTarget",
    "atr",
    "calculate_stop_target",
    "ema",
    "true_ranges",
]
