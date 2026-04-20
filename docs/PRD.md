# Aurus — Product Requirements Document

## Purpose
Aurus is a quantitative trading research and execution system for XAU/USD.

The system is designed to:
- research trading strategies
- validate them with realistic assumptions
- execute trades with strict risk controls
- maintain full auditability

## Non-Goals
- No guaranteed profitability
- No “AI trading system” claims
- No autonomy claims
- No multi-model system in Phase 1

## Phase 1 Goal
Build a deterministic, testable system that:
- runs backtests
- executes paper trades
- enforces risk rules
- logs every decision

## Success Criteria
- positive expectancy after costs (backtest)
- stable performance across datasets
- no crashes in paper trading
- all trades reproducible from logs

## Constraints
- CPU-only environment
- MT5 integration later
- XAU/USD only
