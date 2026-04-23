# Research Specification

## Trading Problem

Identify deterministic XAU/USD trade structures that can produce strong monthly
returns without unsafe leverage.

The immediate research question is:

Can any repeatable chart pattern over six years of M5 data produce close to 10%
monthly return on a 10,000 USD account while risking no more than 2% on the first
trade?

## Inputs
- OHLCV data (5M)
- derived features (ATR, EMA, etc.)
- session information
- six-year historical sample when available
- spread data
- UTC hour and active-session labels

## Output
- deterministic setup definition
- trade ledger with entry, SL, TP, realized R, PnL, and active hour
- monthly PnL and return on 10,000 USD
- active-hour setup quality table
- pass/fail against the 10% monthly research target

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
- monthly return distribution
- losing month count
- average and worst month
- active-hour PnL contribution
- stress performance under higher spread and slippage

## Validation
- walk-forward testing
- out-of-sample testing
- stress test with higher spread
- early / mid / late chronological split
- no promotion when improvement comes only from larger quantity

## Institutional Strategy Reference
- Trend following / time-series momentum is the primary hedge-fund-style baseline
  to test because managed-futures research shows it can explain CTA returns.
- Active-hour and market-structure analysis must be performed before adding any
  new indicator.
