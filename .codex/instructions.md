You are building a quantitative trading research and execution system for XAU/USD.

Core rules:
- Never assume the strategy is profitable.
- Treat all strategy logic as a falsifiable hypothesis.
- Prefer simple, testable logic over sophistication.
- Never add ML unless explicitly asked in the task.
- Never add an LLM to the live execution path unless explicitly asked.
- Every decision must be reproducible from recorded inputs.
- All timestamps must be timezone-aware and stored in UTC.
- All domain logic should be deterministic and testable.
- All broker-specific assumptions must come from metadata, not hardcoded constants.
- All changes must include or update tests.

Architecture priorities:
1. correctness
2. risk control
3. recoverability
4. auditability
5. testability
6. performance

Implementation rules:
- Keep IO behind adapters.
- Keep risk logic pure where possible.
- Use structured logging.
- Preserve replayability.
- Avoid hidden global state.
- Do not silently swallow exceptions.
- Summarize changed files, tests run, and residual risks after each task.
