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

## Sessions
- Asia
- London
- New York
- Rollover

## Rules
- higher timeframe must use closed candles
- no forward-filled future data
