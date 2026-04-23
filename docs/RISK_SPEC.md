# Risk Specification

## Hard Rules
- max daily loss
- max total drawdown
- max trades per day
- mandatory stop loss
- first trade risk must be <= 2% of account equity
- TP distance must be greater than SL distance
- no sizing increase may be treated as strategy improvement

## Filters
- spread threshold
- session filter
- volatility filter
- cooldown after consecutive losses

## Position Sizing
- risk % per trade
- based on stop distance
- use instrument metadata
- default research sizing remains fixed quantity unless a risk-sizing experiment
  is explicitly being tested
- any 10% monthly result must disclose max drawdown and worst month

## Output
RiskDecision:
- allow / deny
- reason
