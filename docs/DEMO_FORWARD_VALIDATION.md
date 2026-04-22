# Demo Forward Validation

Purpose: validate the current Aurus XAU/USD baseline on the MT5 demo account without
claiming live profitability from historical backtests.

## Current Reference

- Data source: MT5 demo account export, `/home/v3ct0r7/xauusd_m5.csv`
- Strategy config: `current_best_real_config()`
- Execution assumptions: `current_best_real_backtest_config()`

## Daily Routine

1. Export the latest MT5 M5 bars.
2. Run the real baseline backtest.
3. Run real validation.
4. Audit data gaps against active strategy windows.
5. Run one paper-forward decision cycle from the latest closed bar.
6. Save artifacts before changing strategy logic.

Commands:

```bash
cd /home/v3ct0r7/Aurus
wine "/home/v3ct0r7/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe" \
  /config:"/home/v3ct0r7/.wine/drive_c/Program Files/MetaTrader 5/export_xauusd_m5.ini"
python -m aurus.ops.run_demo_workflow \
  --data /home/v3ct0r7/xauusd_m5.csv \
  --artifact-dir artifacts/demo-workflow \
  --paper-state-dir artifacts/demo-paper-forward
```

The individual commands remain available for debugging:

```bash
python -m aurus.backtest.run_real_baseline --data /home/v3ct0r7/xauusd_m5.csv
python -m aurus.backtest.validate_real_baseline \
  --data /home/v3ct0r7/xauusd_m5.csv \
  --output artifacts/real-baseline-validation.csv
python -m aurus.backtest.audit_real_gaps \
  --data /home/v3ct0r7/xauusd_m5.csv \
  --output artifacts/real-data-gap-audit.csv
python -m aurus.execution.run_paper_forward \
  --data /home/v3ct0r7/xauusd_m5.csv \
  --state-dir artifacts/demo-paper-forward
```

The paper-forward runner is broker-neutral. It evaluates the latest closed CSV bar only,
routes any signal through the pure risk kernel, submits approved orders to the paper
adapter with an idempotent client order key, and appends decisions to
`artifacts/demo-paper-forward/journal/paper-forward.jsonl`.

## Minimum Evidence Before Live Use

- At least 4 weeks of uninterrupted daily demo exports.
- No unclassified unexpected data gaps during trading windows.
- Positive net PnL and profit factor above 1 on the rolling forward sample.
- Severe-friction stress result remains positive.
- Broker spread distribution remains inside the spread assumptions used in backtests.

## Stop Criteria

- Any week with data gaps inside active London open/mid trading windows.
- Severe-friction PF below 1.
- Rolling forward net PnL below zero after at least 30 completed trades.
- Material change in broker spread regime.
