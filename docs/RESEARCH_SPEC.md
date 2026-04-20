# Research Specification

## Trading Problem

Predict whether price will hit TP before SL within N bars.

## Inputs
- OHLCV data (5M)
- derived features (ATR, EMA, etc.)
- session information

## Output
- probability or binary decision:
  TP hit before SL OR not

## Rules
- no lookahead bias
- features must be point-in-time correct
- no future leakage

## Evaluation
- profit factor
- max drawdown
- expectancy per trade
- win rate
- Sharpe proxy

## Validation
- walk-forward testing
- out-of-sample testing
- stress test with higher spread
