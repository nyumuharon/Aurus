# aurus

`aurus` is a Python 3.11 quantitative trading research and execution system for
XAU/USD.

This repository starts with the package boundaries, tool configuration, and
import tests needed for deterministic research, backtesting, risk control, and
execution work. Strategy logic and machine learning are intentionally omitted.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

