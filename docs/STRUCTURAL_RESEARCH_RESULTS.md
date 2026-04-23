# Structural Research Results

## Scan: Pattern Families v1

Dataset:
- `/home/v3ct0r7/xauusd_m5_dukascopy_6y.csv`
- M5 XAU/USD
- 2020-04-22 through 2026-04-21
- quantity 1

Command:

```bash
python -m aurus.backtest.scan_structural_setups \
  --data /home/v3ct0r7/xauusd_m5_dukascopy_6y.csv \
  --output artifacts/structural-setup-scan.csv \
  --top 15
```

## Families Tested

- Opening range breakout
- Failed breakout reversal
- Impulse continuation

All tests used deterministic entry, SL, TP, and time-exit logic. No ML, no LLM,
and no sizing increase were used.

## Best New Setup

The best new structural setup was:

```text
impulse_continuation:bars=3:atr=0.35:rr=2.5
```

Result:

| Metric | Value |
|---|---:|
| Trades | 1547 |
| PF | 1.1192 |
| Net PnL | 1095.78 |
| Average monthly PnL | 15.01 |
| Worst month | -105.52 |
| Max drawdown | 347.78 |
| Positive months | 42 / 73 |

## Current Baseline To Beat

The current daily trend baseline from active-hour research is:

```text
daily trend 06:00 -> 22:00 UTC, 3R target
```

Result:

| Metric | Value |
|---|---:|
| Trades | 1339 |
| PF | 1.2974 |
| Net PnL | 3064.99 |
| Average monthly PnL | 41.99 |
| Worst month | -258.17 |
| Max drawdown | 700.49 |
| Positive months | 44 / 73 |

## Decision

Do not promote the new structural scan setups yet.

Reason:
- The best impulse-continuation setup has lower PF, lower net PnL, and much lower
  average monthly PnL than the current daily trend baseline.
- Opening range breakout and failed breakout reversal did not produce a stronger
  result in this first deterministic form.
- The impulse setup has better drawdown, so it may be useful later as a secondary
  low-volatility component, but it is not the main strategy needed for the 10%
  monthly research target.

## Next Research Step

Improve structure, not risk:

1. Split the impulse-continuation result by UTC entry hour.
2. Keep only hours where impulse trades are repeatedly positive across early,
   mid, and late segments.
3. Test whether combining the current daily trend baseline with non-overlapping
   high-quality impulse hours improves monthly PnL without materially worsening
   drawdown.
