# Aurus — Project Specification

**Status:** Research-first, deterministic, no-ML Phase 1
**Instrument:** XAU/USD
**Primary dataset:** six-year M5 historical sample where available

## Purpose

Aurus is a quantitative trading research and execution system for XAU/USD.
The current project direction is not an AI/ML trading product. The work is to
analyze six years of charts, identify repeatable structural trade setups, validate
them with realistic costs, and only then paper trade the best candidate with strict
risk controls.

## Current Target

The research target is at least 10% monthly return on a 10,000 USD account without
solving the problem by unsafe leverage. This is a research target, not a promise.
Any candidate must report:

- monthly return distribution
- losing months
- max drawdown
- profit factor
- trade count
- stress results with wider spread and slippage
- first-trade risk no greater than 2% of account equity

## Non-Goals

- No guaranteed profitability.
- No ML in Phase 1.
- No LLM in the execution path.
- No autonomy claims.
- No increasing position size to hide weak strategy structure.
- No adding random indicators without structural justification.

## Research Foundation

Institutional managed-futures and CTA research commonly uses systematic
trend-following / time-series momentum. AQR research describes managed futures as
simple trend-following strategies that go long markets with positive prior returns
and short markets with negative prior returns. Hurst, Ooi, and Pedersen also
documented trend-following evidence across global markets since 1880.

For gold-specific microstructure, CME notes that COMEX GC trades nearly 24 hours
and has meaningful liquidity across Asia, London, and New York. Aurus therefore
must not assume London-only is always best. Active-hour analysis is a required
research output.

## Phase 1 Architecture

| Layer | Responsibility |
|---|---|
| Data | Load, clean, normalize, and audit XAU/USD M5 data |
| Research | Analyze chart structure, active hours, volatility, trend behavior, and setup outcomes |
| Strategy | Encode one deterministic setup at a time |
| Backtest | Replay bars with spread/slippage, SL/TP, equity curve, and trade ledger |
| Risk | Enforce max risk, drawdown, spread, session, and stop-loss rules |
| Execution | Paper adapter first; MT5 integration later |
| Observability | Event journal, trade ledger, metrics, and reproducible summaries |

## Required Research Outputs

Before promoting a setup, produce:

- yearly PnL and monthly PnL on a 10,000 USD account
- active-hour table by UTC hour
- trade setup cohort table by hour, direction, volatility, and trend state
- first-trade risk at or below 2%
- TP distance greater than SL distance, with RR reported
- stress results under normal, moderate, and severe costs
- clear rejection of failed structures

## Current Implemented Research Branch

The current daily trend branch is:

- entry: 06:00 UTC
- exit: 22:00 UTC
- direction: 1H EMA trend
- stop: 3x 1H ATR
- target: 3R
- quantity default: 1

This branch is profitable in the six-year sample but does not meet the 10% monthly
target at quantity 1. It remains a baseline to beat, not a finished strategy.

## Risk Rules

- First trade risk must not exceed 2% of account equity.
- Stop loss is mandatory.
- TP must be farther from entry than SL in distance terms.
- Position sizing must be based on account equity, stop distance, and instrument metadata.
- No strategy may be promoted by increasing size alone.
- Drawdown and stress survival must be reported before paper trading.

## References

- Hurst, Ooi, and Pedersen, "A Century of Evidence on Trend-Following Investing":
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- AQR, "Demystifying Managed Futures":
  https://www.aqr.com/Insights/Research/Journal-Article/Demystifying-Managed-Futures
- CME Group, "Trading COMEX Gold and Silver":
  https://www.cmegroup.com/education/articles-and-reports/trading-comex-gold-and-silver
