# Aurus Structural Research Plan

## Objective

Find a stronger XAU/USD trade structure from six years of M5 charts. The target is
10% monthly return on a 10,000 USD account, but the strategy cannot reach that by
increasing quantity alone. The work must improve setup quality and opportunity
selection.

## Required Constraints

- XAU/USD only.
- No ML.
- No LLM in signal generation or execution.
- Quantity 1 for structural research unless explicitly testing risk sizing.
- First trade risk must be <= 2% of equity.
- TP distance must be greater than SL distance.
- Every setup must include deterministic entry, SL, TP, and exit rules.

## External Research Baseline

Institutional managed-futures research supports trend following / time-series
momentum as the first structure to test. AQR describes managed futures as simple
time-series momentum: long markets with positive prior returns and short markets
with negative prior returns. Hurst, Ooi, and Pedersen document trend-following
evidence across global markets since 1880.

CME gold volume research also shows meaningful activity outside a single London
window, including Asia-hour liquidity. Aurus must therefore analyze UTC hours from
the actual six-year dataset instead of assuming one session is best.

## Pattern Families To Test

1. Trend continuation after impulse
   - 1H trend direction
   - M5 impulse expansion
   - controlled pullback or continuation candle
   - structural or ATR stop

2. Opening range breakout
   - Asia range
   - pre-London range
   - London initial balance
   - New York opening range
   - structure stop beyond range

3. Failed breakout reversal
   - active-hour sweep of prior range
   - close back inside range
   - stop beyond sweep extreme
   - fixed RR target

4. Trend acceleration pullback
   - EMA slope acceleration
   - ATR expansion
   - pullback depth bounded by ATR
   - confirmation in trend direction

## Active-Hour Analysis

For each UTC hour, report:

- candidate setups
- completed trades
- win rate
- PF
- net PnL
- average R
- worst month contribution
- average spread

Only hours with repeated positive contribution across early, mid, and late segments
should become default trading windows.

## Promotion Rules

A setup can become the new baseline only if it improves at least three of:

- average monthly PnL at quantity 1
- profit factor
- max drawdown
- severe-friction survival
- positive month percentage
- early / mid / late stability

It must not reduce the research to a tiny number of trades, and it must not rely on
larger quantity to look good.

## References

- Hurst, Ooi, Pedersen, "A Century of Evidence on Trend-Following Investing":
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- AQR, "Demystifying Managed Futures":
  https://www.aqr.com/Insights/Research/Journal-Article/Demystifying-Managed-Futures
- CME Group, "Trading COMEX Gold and Silver":
  https://www.cmegroup.com/education/articles-and-reports/trading-comex-gold-and-silver
