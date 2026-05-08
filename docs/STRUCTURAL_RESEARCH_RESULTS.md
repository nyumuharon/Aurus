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

## Scan: Impulse Continuation By UTC Hour

Command:

```bash
python -m aurus.backtest.analyze_impulse_hours \
  --data /home/v3ct0r7/xauusd_m5_dukascopy_6y.csv \
  --output artifacts/impulse-hour-analysis.csv \
  --top 20
```

Best robust row with at least 100 trades:

| Hour UTC | Parameters | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD |
|---:|---|---:|---:|---:|---:|---:|---:|
| 06 | impulse_continuation:bars=12:atr=0.75:rr=3.0 | 531 | 1.2165 | 774.94 | 10.62 | -168.05 | 250.96 |

Decision:
- Do not promote impulse continuation as the main branch.
- The best robust impulse hour is useful but weaker than the daily trend baseline.
- High-PF rows at 12, 16, and 20 UTC were too small to trust.
- The 06 UTC impulse signal overlaps the current daily trend entry hour, so it
  should not simply be added as another same-direction trade without a portfolio
  conflict rule.

## Risk-Normalized Daily Trend Check

Command:

```bash
python -m aurus.backtest.risk_normalized_daily_trend \
  --data /home/v3ct0r7/xauusd_m5_dukascopy_6y.csv \
  --output artifacts/daily-trend-risk-normalized.csv \
  --starting-equity 10000
```

Result:

| Risk / Trade | Ending Equity | Avg Monthly Return | Best Month | Worst Month | Months >= 10% | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5% | 15673.19 | 0.78% | 10.62% | -4.70% | 1 / 73 | 23.04% |
| 1.0% | 23367.20 | 1.83% | 30.74% | -9.35% | 5 / 73 | 47.08% |
| 2.0% | 44832.22 | 4.77% | 111.60% | -22.50% | 17 / 73 | 96.31% |
| Progressive 2.0% -> 5.0% | 49612.48 | 5.43% | 190.05% | -23.96% | 16 / 73 | 100.79% |
| Progressive 2.0% -> 8.0% | 33931.26 | 3.28% | 148.46% | -18.97% | 15 / 73 | 106.65% |
| Progressive 2.0% -> 10.0% | 41446.43 | 4.31% | 194.89% | -20.02% | 15 / 73 | 99.20% |

Decision:
- Even at the maximum allowed 2% risk per trade, the current structure does not
  produce consistent 10% monthly returns.
- Progressive risk starting at 2% also does not produce consistent 10% monthly
  returns. It increases upside, but drawdown becomes close to or above the account
  starting equity.
- The 2% and progressive variants have unacceptable drawdown for a 10,000 USD account.
- The next improvement must come from new structure, not risk scaling.

## Scan: Daily Channel Breakouts

Command:

```bash
python -m aurus.backtest.scan_channel_breakouts \
  --data /home/v3ct0r7/xauusd_m5_dukascopy_6y.csv \
  --output artifacts/channel-breakout-scan.csv \
  --top 20
```

Best channel-breakout row:

| Parameters | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|
| daily_channel_breakout:hours=72:start=7:exit=22:stop=atr2.0:rr=2.0 | 804 | 1.2850 | 1180.91 | 16.18 | -125.85 | 324.89 | 39 / 73 |

Decision:
- Do not replace the daily trend baseline with channel breakout.
- The best channel-breakout result is profitable and has controlled drawdown, but
  it is weaker than the daily trend baseline on net PnL and average monthly PnL.
- It is still useful as a candidate second component because it is a different
  structural expression of trend expansion: previous multi-day channel break,
  ATR stop, fixed RR target.

## Portfolio Check: Daily Trend + Channel Breakout

Command:

```bash
python -m aurus.backtest.analyze_structure_portfolio \
  --data /home/v3ct0r7/xauusd_m5_dukascopy_6y.csv \
  --output artifacts/structure-portfolio-trades.csv
```

Result:

| Component | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|
| Daily trend | 1339 | 1.2974 | 3064.99 | 41.99 | -258.17 | 631.75 | 44 / 73 |
| Channel breakout | 804 | 1.2850 | 1180.91 | 16.18 | -125.85 | 324.89 | 39 / 73 |
| Combined | 2143 | 1.2939 | 4245.90 | 58.16 | -207.07 | 645.98 | 42 / 73 |

Decision:
- The combined structure improves fixed-size net PnL and average monthly PnL
  without reducing PF materially.
- It does not yet meet the 10% monthly target on a 10,000 USD account using
  fixed quantity 1.
- This is the best direction found so far: increase structurally different
  profitable opportunities instead of increasing risk on the same fragile signal.
- Next research should test another independent structure and then evaluate
  portfolio interaction, not loosen the same entry repeatedly.

## Third Component: Selective NY Impulse

The best third component found from the existing scan families is a selective
New York impulse-continuation slice:

```text
impulse_continuation:bars=12:atr=0.75:rr=2.5:hour=12
```

Standalone result:

| Component | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|
| NY impulse | 53 | 4.4628 | 499.56 | 15.14 | -19.47 | 57.13 | 20 / 33 |

Three-component fixed-size portfolio:

| Component | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|
| Daily trend | 1339 | 1.2974 | 3064.99 | 41.99 | -258.17 | 631.75 | 44 / 73 |
| Channel breakout | 804 | 1.2850 | 1180.91 | 16.18 | -125.85 | 324.89 | 39 / 73 |
| NY impulse | 53 | 4.4628 | 499.56 | 15.14 | -19.47 | 57.13 | 20 / 33 |
| Combined | 2196 | 1.3252 | 4745.46 | 65.01 | -193.33 | 645.98 | 43 / 73 |

Risk-normalized portfolio result on a 10,000 USD account:

| Risk / Trade | Ending Equity | Avg Monthly Return | Best Month | Worst Month | Months >= 10% | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5% | 20391.08 | 1.42% | 15.72% | -7.33% | 3 / 73 | 31.65% |
| 1.0% | 38448.17 | 3.90% | 56.80% | -14.28% | 14 / 73 | 60.52% |
| 2.0% | 108478.31 | 13.49% | 295.97% | -26.75% | 22 / 73 | 119.20% |
| Progressive 2.0% -> 5.0% | 341989.41 | 45.48% | 1443.79% | -67.84% | 22 / 73 | 472.12% |

Decision:
- This third component improves fixed-size portfolio PF, net PnL, average monthly
  PnL, and worst-month behavior.
- It is a useful structural diversification leg because it trades a narrow NY
  continuation state rather than another all-day trend stream.
- It still does not make the portfolio safely capable of consistent 10% monthly
  returns. The only way to produce many 10% months here is still to size into
  unacceptable drawdown.
- The next improvement must again come from structure quality, ideally another
  component with better downside offset rather than a higher-variance trend leg.

## Fourth Component: Selective London Reversal

The reversal family was broadly weak, but one narrow slice was useful as a
downside-offset component:

```text
failed_breakout_reversal:pre_london:rr=3.0:hour=13
```

Standalone result:

| Component | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|
| London reversal | 32 | 1.8263 | 66.00 | 2.87 | -11.12 | 49.76 | 8 / 23 |

Four-component fixed-size portfolio:

| Component | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|
| Daily trend | 1339 | 1.2974 | 3064.99 | 41.99 | -258.17 | 631.75 | 44 / 73 |
| Channel breakout | 804 | 1.2850 | 1180.91 | 16.18 | -125.85 | 324.89 | 39 / 73 |
| NY impulse | 53 | 4.4628 | 499.56 | 15.14 | -19.47 | 57.13 | 20 / 33 |
| London reversal | 32 | 1.8263 | 66.00 | 2.87 | -11.12 | 49.76 | 8 / 23 |
| Combined | 2228 | 1.3279 | 4811.46 | 65.91 | -193.33 | 617.35 | 42 / 73 |

Risk-normalized portfolio result on a 10,000 USD account:

| Risk / Trade | Ending Equity | Avg Monthly Return | Best Month | Worst Month | Months >= 10% | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5% | 19685.53 | 1.33% | 17.85% | -8.34% | 3 / 73 | 33.24% |
| 1.0% | 35756.95 | 3.53% | 61.73% | -16.29% | 14 / 73 | 63.54% |
| 2.0% | 93034.24 | 11.37% | 292.91% | -30.74% | 18 / 73 | 113.75% |
| Progressive 2.0% -> 5.0% | 249348.17 | 32.79% | 1112.80% | -30.79% | 19 / 73 | 309.65% |

Decision:
- The selective reversal slice is worth keeping because it improves the portfolio
  PF and lowers fixed-size drawdown from 645.98 to 617.35.
- It also lowers the 2% fixed-risk max drawdown from 119.20% to 113.75%.
- This is still not enough to make the portfolio safely capable of 10% monthly
  returns in a tradeable way.
- The next component should again prioritize diversification and downside offset,
  not another correlated trend-expansion leg.

## Research Check: Compression Breakout

Tested structure:

```text
compression_breakout:pre_london_to_ny_open:atr=1.0:rr=2.0
```

Standalone result:

| Component | Trades | PF | Net PnL | Max DD |
|---|---:|---:|---:|---:|
| Compression breakout | 367 | 1.2726 | 271.61 | 87.65 |

Portfolio impact when added to the current 4-component portfolio:

| Portfolio | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| Current 4-component | 2228 | 1.3279 | 4811.46 | 65.91 | -193.33 | 617.35 |
| Plus compression breakout | 2595 | 1.3244 | 5083.07 | 69.63 | -190.66 | 635.19 |

Decision:
- Do not promote the compression-breakout sleeve.
- It adds net PnL and average monthly PnL, but it slightly lowers PF and increases
  drawdown versus the current 4-component portfolio.
- This suggests it is still too correlated with the existing trend-expansion legs.
- Keep the scanner as a research tool, but do not add this sleeve to the live
  reference portfolio.

## Research Family Failure: Session-Open Mean Reversion

Family tested:
- fade an oversized move away from a session open or early session base
- require a later stall candle
- exit on fixed RR or time stop

This family was tested across:
- Asia to London
- pre-London to mid-session
- London open / initial-balance to mid-session
- London open / initial-balance to New York
- New York open to late session

Best corrected family slice:

```text
session_run_reversal:pre_london_to_mid:atr=3.0:rr=3.0
```

Standalone result:

| Component | Trades | PF | Net PnL | Avg Monthly PnL | Worst Month | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| Session run reversal | 91 | 1.5906 | 74.61 | 1.52 | -10.53 | 26.20 |

Why the family still fails your target:
- No tested slice produced all-positive months in its evaluation window.
- No tested slice produced consistent >=10% monthly returns on a risk-normalized
  account with small drawdown.
- When promoted into the reference portfolio, the family could improve fixed-size
  PF slightly, but account-level drawdown expanded materially once risk was sized
  to the return target.

Decision:
- Conclusively fail this research family against the target:
  all months positive, monthly returns consistently >=10%, and super-small drawdown.
- Keep `scan_session_run_reversal(...)` only as a research utility.
- Do not include this family in the reference portfolio.
