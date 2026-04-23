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
- analyzes six years of XAU/USD chart structure before promoting a strategy
- reports yearly and monthly performance on a 10,000 USD account
- identifies active UTC hours where good setups actually occur

## Success Criteria
- positive expectancy after costs (backtest)
- research target: at least 10% monthly return without unsafe leverage
- stable monthly performance across early, mid, and late historical segments
- no crashes in paper trading
- all trades reproducible from logs
- first-trade risk no greater than 2% of account equity
- TP distance greater than SL distance on every entry

## Constraints
- CPU-only environment
- MT5 integration later
- XAU/USD only
- no ML or LLM in Phase 1 strategy logic
- do not solve weak edge by increasing position size
