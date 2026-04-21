# Backtest Specification

## Engine Type
Event-driven backtest engine.

## Requirements
- sequential bar replay
- no lookahead
- deterministic results

## Execution Model
- include spread
- include slippage
- simulate order fills

## Trade Logic
- entry at bar close or next open
- SL and TP enforced
- optional stop tightening can move stops to breakeven after +0.5R and trail at +0.25R after +1.0R

## Outputs
- trade log
- equity curve
- PnL summary

## Metrics
- profit factor
- drawdown
- win rate
- average R
