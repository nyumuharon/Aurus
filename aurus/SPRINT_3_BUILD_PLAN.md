# Aurus — Sprint 3 Agent Build Plan
## AI Validator — Staged Construction

**Version:** 1.0
**Sprint:** 3 of 6
**Senior Principal Engineer:** Claude
**Lead Engineer:** Haron
**Goal:** Build the AI validator that takes ensemble signals from Layer 2, validates them against market context using Qwen3:8b via Ollama, and passes clean YES/NO decisions to Layer 4.

---

## Critical Rules for the Agent

- Build **one stage at a time** — do not jump ahead
- After each stage, run the tests for that stage only
- Only proceed to the next stage when every test passes
- Every function must have a docstring
- Every function must have try/except error handling
- Every file must have a module-level comment block at the top
- No hardcoded values — all constants come from `config/settings.py`
- Never use `print()` for errors — use Python `logging` module only
- **Default to NO on any failure, ambiguity, or uncertainty — never default to YES**
- Every validation decision must be logged regardless of outcome
- Timeout for Ollama calls is 30 seconds maximum

---

## Architecture Reminder

```
Ensemble Signal + Market Context
          |
          v
[ prompt_builder.py ]   <- Stage 1
  - Formats signal, news, DXY, calendar
  - Returns structured prompt string
          |
          v
[ ai_validator.py ]     <- Stage 2
  - Checks Ollama is running
  - Sends prompt to Qwen3:8b
  - Receives raw response
  - Parses YES or NO
  - Logs decision
  - Returns validation result dict
          |
          v
Layer 4 - Risk Manager (Sprint 4)
```

---

## File Structure Being Built

```
aurus/
  src/
    validator/
      __init__.py
      prompt_builder.py     <- Stage 1
      ai_validator.py       <- Stage 2
  tests/
    test_prompt_builder.py  <- Stage 1 test
    test_ai_validator.py    <- Stage 2 test
```

---

## Dependencies to Add to `requirements.txt`

Add this line to the existing `requirements.txt` under a Sprint 3 comment:

```
# -- Sprint 3 - AI Validator ------------------------------------------
ollama==0.2.1
```

Install with:

```bash
pip install ollama==0.2.1
```

---

## Constants to Add to `config/settings.py`

Append the following block to the bottom of the existing `settings.py`:

```python
# -- Sprint 3 - AI Validator ------------------------------------------

# Ollama connection
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_TIMEOUT_SECONDS = 30
OLLAMA_MAX_RETRIES = 1

# Validator behaviour
VALIDATOR_DEFAULT_DECISION = "NO"       # always NO on failure
VALIDATOR_LOG_FILE = "logs/validator.log"
VALIDATOR_MIN_CONFIDENCE = 0.60         # minimum ensemble score to validate

# Prompt settings
PROMPT_MAX_HEADLINES = 3                # max news headlines in prompt
PROMPT_CALENDAR_WINDOW_HOURS = 4        # look ahead window for events
```

---

## Stage 1 - Prompt Builder (`prompt_builder.py`)

**Build this first. The validator depends on it.**

### What this module does

Takes raw data from the ensemble signal and the Data Manager market snapshot and builds a single structured prompt string ready to send to Qwen3:8b. This module contains zero AI logic — it only formats data into text.

### File to create

`src/validator/prompt_builder.py`

### Prompt template

The prompt must follow this exact structure:

```
You are a professional gold (XAU/USD) trading analyst.
Analyze this trade signal and decide if it is safe to take.

SIGNAL: {BUY | SELL}
CONFIDENCE SCORE: {weighted_score:.2f}
ENTRY PRICE: {price:.2f}
DXY BIAS: {BULLISH | BEARISH | NEUTRAL}

MODEL AGREEMENT:
  - LSTM:          {signal} ({confidence:.0%})
  - TFT:           {signal} ({confidence:.0%})
  - Random Forest: {signal} ({confidence:.0%})
  - SMC Detector:  {signal} ({confidence:.0%})

RECENT NEWS:
  - {headline_1}
  - {headline_2}
  - {headline_3}

UPCOMING HIGH IMPACT EVENTS: {events | "None in the next 4 hours"}

RULES:
  - Reply YES if the signal aligns with current news and context
  - Reply NO if news contradicts the signal direction
  - Reply NO if a HIGH impact event occurs within the next 15 minutes
  - Reply NO if DXY bias strongly contradicts the signal
  - Your entire response must be ONLY one of these two formats:
      YES: one sentence explaining why
      NO: one sentence explaining why
  - No preamble. No extra text. No markdown.
```

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `build_prompt(ensemble_signal, market_snapshot)` | Build complete prompt from signal and snapshot | `str` |
| `format_signal_section(ensemble_signal)` | Format the signal, score, price section | `str` |
| `format_model_section(ensemble_signal)` | Format individual model votes section | `str` |
| `format_news_section(news_list)` | Format top 3 headlines section | `str` |
| `format_calendar_section(calendar_data)` | Format upcoming events section | `str` |
| `validate_inputs(ensemble_signal, market_snapshot)` | Check all required fields exist | `True` or `False` |

### Input structures

**ensemble_signal** (from Layer 2):
```python
{
    "timestamp": "2026-03-01 10:00:00",
    "final_signal": "BUY",
    "weighted_score": 0.73,
    "individual_signals": {
        "lstm":          {"signal": "BUY",     "confidence": 0.82},
        "tft":           {"signal": "BULLISH", "confidence": 0.74},
        "random_forest": {"signal": "BUY",     "confidence": 0.65},
        "smc_detector":  {"signal": "BUY",     "confidence": 0.75}
    }
}
```

**market_snapshot** (from Layer 1 Data Manager):
```python
{
    "price": {
        "latest_candle": {"close": 2988.75, ...}
    },
    "news": [
        {"headline": "...", "sentiment": "bearish"},
        ...
    ],
    "dxy": {"trend": "BEARISH", "price": 104.32},
    "calendar": {
        "events_today": [...],
        "high_impact_window": False
    }
}
```

### Error handling rules

- If `ensemble_signal` is None or missing required keys -> log error, return empty string `""`
- If `market_snapshot` is None -> log error, return empty string `""`
- If news list is empty -> use `"No recent news available"` in prompt
- If calendar events are empty -> use `"None in the next 4 hours"` in prompt
- Never raise an exception — always return a string

### Stage 1 Test (`tests/test_prompt_builder.py`)

```
1.  build_prompt() returns a non-empty string with valid inputs
2.  Returned prompt contains the signal direction (BUY or SELL)
3.  Returned prompt contains the confidence score
4.  Returned prompt contains DXY bias
5.  Returned prompt contains at least one news headline
6.  Returned prompt contains the RULES section
7.  validate_inputs() returns True for valid inputs
8.  validate_inputs() returns False when ensemble_signal is None
9.  validate_inputs() returns False when market_snapshot is None
10. build_prompt() returns empty string when inputs are invalid
11. format_news_section() handles empty news list gracefully
12. format_calendar_section() handles empty events gracefully
```

### Stage 1 Acceptance Check

```
src/validator/__init__.py created                     [ ]
prompt_builder.py exists in src/validator/            [ ]
All 6 functions implemented                           [ ]
All functions have docstrings                         [ ]
Prompt matches required template structure            [ ]
test_prompt_builder.py exists in tests/               [ ]
All 12 tests passing                                  [ ]
Sample prompt prints correctly to terminal            [ ]
```

**Do not proceed to Stage 2 until all are checked.**

---

## Stage 2 - AI Validator (`ai_validator.py`)

**Depends on:** Stage 1 complete and accepted

### What this module does

The core validation engine. Connects to Ollama, sends the prompt built by `prompt_builder.py`, receives the raw LLM response, parses it into a clean YES or NO decision, logs the full decision with context, and returns a structured result dictionary to Layer 4.

### File to create

`src/validator/ai_validator.py`

### Functions to implement

| Function | Description | Returns |
|---|---|---|
| `check_ollama_connection()` | Verify Ollama is running and model is available | `True` or `False` |
| `send_prompt(prompt)` | Send prompt to Qwen3:8b and get raw response | `str` or `None` |
| `parse_response(raw_response)` | Extract YES/NO and reason from raw response | `dict` |
| `validate(ensemble_signal, market_snapshot)` | Full validation pipeline | `dict` |
| `log_decision(validation_result)` | Log full decision to file and SQLite | `None` |
| `get_default_no(reason)` | Return a standard NO result for error cases | `dict` |

### Output format of `validate()`

```python
{
    "timestamp": "2026-03-01 10:00:00",
    "signal": "BUY",
    "validated": True,           # True = YES, False = NO
    "decision": "YES",           # "YES" or "NO"
    "reason": "Signal aligns with bearish DXY and dovish Fed news.",
    "raw_response": "YES: Signal aligns with bearish DXY...",
    "model": "qwen3:8b",
    "latency_ms": 420,
    "passed_to_risk": True       # True only if validated = True
}
```

### Output format of `get_default_no()`

```python
{
    "timestamp": "2026-03-01 10:00:00",
    "signal": "UNKNOWN",
    "validated": False,
    "decision": "NO",
    "reason": reason,
    "raw_response": None,
    "model": "qwen3:8b",
    "latency_ms": 0,
    "passed_to_risk": False
}
```

### Response parsing rules

The LLM is instructed to reply in one of two formats:
```
YES: one sentence reason
NO: one sentence reason
```

Parsing logic:

```python
# IMPORTANT: Qwen3 uses <think> tags before answering
# Strip everything inside <think>...</think> first
# Then parse the remaining text

import re

def parse_response(raw_response):
    # Step 1: Remove think tags and their content
    cleaned = re.sub(r'<think>.*?</think>', '', raw_response,
                     flags=re.DOTALL).strip()

    # Step 2: Find YES or NO line
    response_upper = cleaned.upper()

    if response_upper.startswith("YES"):
        decision = "YES"
        validated = True
        reason = cleaned[4:].strip()

    elif response_upper.startswith("NO"):
        decision = "NO"
        validated = False
        reason = cleaned[3:].strip()

    else:
        # Search for YES/NO anywhere in cleaned response
        if "YES" in response_upper:
            decision = "YES"
            validated = True
            reason = "Extracted from response"
        elif "NO" in response_upper:
            decision = "NO"
            validated = False
            reason = "Extracted from response"
        else:
            decision = "NO"
            validated = False
            reason = "LLM response could not be parsed — defaulting to NO"

    return {"decision": decision, "validated": validated, "reason": reason}
```

### Connection check logic

```python
def check_ollama_connection():
    # Call ollama.list() to check server is running
    # Check OLLAMA_MODEL name appears in the returned models
    # Return True only if both conditions are met
    # Return False and log error if anything fails
    # Never raise — always return bool
```

### Timeout handling

```python
# Wrap all ollama.chat() calls in a thread with timeout
# If OLLAMA_TIMEOUT_SECONDS exceeded:
#   log error
#   retry once
#   if retry also times out: return get_default_no("Response timeout")
```

### Logging requirements

Every call to `validate()` must log this line:

```
[2026-03-01 10:00:00] SIGNAL=BUY | DECISION=YES | SCORE=0.73 | LATENCY=420ms | REASON=Signal aligns...
```

Log to both:
- `logs/validator.log` using Python `logging.handlers.RotatingFileHandler` (max 10MB, 3 backups)
- SQLite table `validator_decisions` with these exact columns:
  ```sql
  CREATE TABLE IF NOT EXISTS validator_decisions (
      id        INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      signal    TEXT NOT NULL,
      decision  TEXT NOT NULL,
      reason    TEXT,
      score     REAL,
      latency   INTEGER,
      model     TEXT
  );
  ```

### Error handling rules

| Failure | Action |
|---|---|
| Ollama not running | Log critical, return `get_default_no("Ollama not available")` |
| Model not found | Log critical, return `get_default_no("Model not found")` |
| Response timeout | Log error, retry once, return `get_default_no("Timeout")` |
| Unparseable response | Log warning, return `get_default_no("Parse error")` |
| Empty prompt from builder | Log error, return `get_default_no("Empty prompt")` |
| Any unhandled exception | Log critical with traceback, return `get_default_no("Unexpected error")` |

### Stage 2 Test (`tests/test_ai_validator.py`)

```
1.  check_ollama_connection() returns True when Ollama is running
2.  check_ollama_connection() returns False when Ollama is not running (mock)
3.  send_prompt() returns a non-empty string for valid prompt
4.  send_prompt() returns None on timeout (mock)
5.  parse_response() returns YES decision for "YES: reason" input
6.  parse_response() returns NO decision for "NO: reason" input
7.  parse_response() returns NO decision for unparseable input
8.  parse_response() strips think tags before parsing
9.  parse_response() extracts reason correctly from YES response
10. parse_response() extracts reason correctly from NO response
11. validate() returns dict with all required keys
12. validate() returns validated=True for a clear BUY signal (integration)
13. validate() returns validated=False when Ollama is down (mock)
14. validate() returns validated=False when prompt is empty
15. get_default_no() returns correct structure with validated=False
16. log_decision() writes to log file without error
17. log_decision() writes to SQLite without error
```

### Stage 2 Acceptance Check

```
ai_validator.py exists in src/validator/              [ ]
All 6 functions implemented                           [ ]
Ollama connection check working                       [ ]
Prompt sent and response received from Qwen3:8b       [ ]
Think tags stripped before parsing                    [ ]
YES/NO parsing working correctly                      [ ]
Default NO on all failure modes                       [ ]
Logging to file working                               [ ]
SQLite logging working                                [ ]
test_ai_validator.py exists in tests/                 [ ]
All 17 tests passing                                  [ ]
Live validation result prints to terminal             [ ]
All code committed to GitHub                          [ ]
```

---

## Sprint 3 Final Acceptance

Sprint 3 is closed only when every stage acceptance check is complete:

```
Stage 1 - Prompt Builder        [ ]
Stage 2 - AI Validator          [ ]
All 29 tests passing            [ ]
Live end-to-end validation      [ ]
All code on GitHub              [ ]
```

### End-to-End Validation Test

Before closing Sprint 3, run this manually to confirm the full pipeline works:

```python
from src.validator.ai_validator import validate
from src.models.ensemble import get_ensemble_signal
from src.data.data_manager import get_market_snapshot

signal = get_ensemble_signal()
snapshot = get_market_snapshot()
result = validate(signal, snapshot)

print(result)
```

The output must:
- Be a complete dict with all required keys
- Have `decision` equal to `"YES"` or `"NO"`
- Have a non-empty `reason` string
- Have `latency_ms` greater than 0

When this runs cleanly — Sprint 3 is closed.

---

## Critical Reminder: Think Tags

Qwen3:8b uses chain-of-thought reasoning. It wraps its thinking in `<think>...</think>` tags before giving the final answer. Example raw response:

```
<think>
The signal is BUY on gold. DXY is bearish which supports gold.
News shows Fed is dovish. No high impact events upcoming.
This looks like a valid setup.
</think>
YES: DXY weakness and dovish Fed stance support a long gold position.
```

The parser MUST strip the think block and only parse the final line. Failing to do this will cause every response to be unparseable.

---

*Aurus Sprint 3 - AI Validator. One question. Two answers. No exceptions.*
