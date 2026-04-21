# aurus

`aurus` is a Python 3.11 quantitative trading research and execution system for
XAU/USD.

This repository contains deterministic research, backtesting, risk-control,
paper-execution, and observability primitives for the Phase 1 XAU/USD system.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Baseline Backtest

From the repository root:

```bash
source .venv/bin/activate
python -m aurus.backtest.run_baseline \
  --context-ema-period 3 \
  --execution-ema-period 3 \
  --atr-period 3 \
  --min-atr 0.50 \
  --max-spread 0.50
```

By default this loads `examples/baseline_sample_bars.csv`, creating that sample
dataset if it is missing, and writes:
- `artifacts/baseline-trades.csv`
- `artifacts/baseline-events.jsonl`

To run against the larger deterministic fixture:

```bash
python -m aurus.backtest.run_baseline --large-sample
```

To run the deterministic baseline parameter sweep:

```bash
python -m aurus.backtest.sweep_baseline
```

To run the baseline execution-friction stress test:

```bash
python -m aurus.backtest.stress_baseline
```

## Real XAU/USD CSV

Real 5-minute historical data can be loaded from a CSV with this format:

```text
timestamp,open,high,low,close,volume,spread
2026-01-05T00:00:00Z,2640.10,2641.20,2639.80,2640.60,120,0.25
```

`spread` is optional. Timestamps are parsed as timezone-aware UTC, rows are
sorted, duplicate timestamps are removed deterministically, missing 5-minute
bars are reported, and closed 1-hour context bars are derived from the 5-minute
series.

```bash
python -m aurus.backtest.run_real_baseline --data path/to/xauusd_5m.csv
```

If the CSV has no spread column, provide a deterministic fallback:

```bash
python -m aurus.backtest.run_real_baseline --data path/to/xauusd_5m.csv --fallback-spread 0.25
```

## MetaTrader 5 Export

On the machine where MetaTrader 5 is installed and logged in:

```bash
python -m pip install -e ".[mt5]"
python -m aurus.data.mt5_export \
  --symbol XAUUSD \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z \
  --output data/xauusd_m5.csv
```

If the terminal is not already discoverable by the MetaTrader5 Python package,
pass `--terminal-path`, and optionally `--login`, `--password`, and `--server`.
