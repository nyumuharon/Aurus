"""Backtesting package for reproducible historical evaluation."""

from aurus.backtest.engine import BacktestEngine
from aurus.backtest.interfaces import RiskEngine, StrategyCallback
from aurus.backtest.placeholder import COMPONENT
from aurus.backtest.risk import ApproveAllRiskEngine
from aurus.backtest.types import BacktestConfig, BacktestResult, EquityPoint, TradeRecord

__all__ = [
    "COMPONENT",
    "ApproveAllRiskEngine",
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "EquityPoint",
    "RiskEngine",
    "StrategyCallback",
    "TradeRecord",
]
