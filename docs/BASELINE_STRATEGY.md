# Baseline Strategy

## Instrument
XAU/USD

## Timeframes
- execution: 5M
- trend: 1H

## Filters
- trend: EMA50 direction (1H)
- trend quality: normalized 1H EMA slope, optional threshold
- volatility: ATR threshold
- volatility strength: ATR divided by price, optional threshold
- regime: 1H ATR divided by price, optional threshold
- session: London + NY, with optional London open/mid/late subwindow allowlist
- spread: must be below threshold

## Entry (Pullback)
Default `entry_mode=baseline` keeps the original pullback entry:

Long:
- 1H bullish
- price pulls back to EMA20 (5M)
- optional minimum pullback depth, measured as EMA penetration divided by ATR
- bullish confirmation candle

Short:
- inverse

Optional `entry_mode=early_momentum` tests earlier trend-continuation entries:
- 1H trend remains confirmed
- price closes on the trend side of the 5M EMA
- candle closes in the direction of the trend
- no pullback requirement

Optional `entry_mode=trend_continuation` keeps 1H trend alignment while allowing more
continuation entries:
- price closes on the trend side of the 5M EMA
- candle closes in the trend direction, or price makes a small EMA-band pullback
- strict EMA touch by the previous candle is not required

## Stop Loss
- below/above swing
- ATR floor optional

## Take Profit
- fixed 2R

## Position Sizing
- fixed % risk per trade

## Notes
- deterministic
- no ML
- no LLM
