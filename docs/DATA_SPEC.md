# Data Specification

## Sources
- XAU/USD OHLCV
- spread data
- session labels

## Requirements
- timestamps in UTC
- no duplicate timestamps
- no missing bars (flag if missing)

## Data Model
Each bar must include:
- timestamp
- open
- high
- low
- close
- volume
- spread

## Real 5M CSV Format
Historical XAU/USD 5-minute CSV imports use:

```text
timestamp,open,high,low,close,volume,spread
```

`spread` is optional. Timestamps must be timezone-aware and are normalized to UTC.
Rows are sorted by timestamp, duplicate timestamps are removed deterministically,
missing 5-minute bars are flagged, and closed 1-hour context candles are derived
from complete calendar-hour windows only.

MT5 CSV exports may provide XAU/USD spread as integer points. Those values are
normalized to price units using `spread_price = spread_points * 0.01`; decimal
spread values are treated as already normalized price units.

## Sessions
- Asia
- London
- New York
- Rollover

## Rules
- higher timeframe must use closed candles
- no forward-filled future data
