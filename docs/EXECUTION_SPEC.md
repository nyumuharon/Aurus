# Execution Specification

## Responsibilities
- order creation
- position tracking
- execution simulation

## Requirements
- idempotent order submission
- retry logic
- order validation
- structured logging

## States
- pending
- filled
- closed
- rejected

## Constraints
- no direct broker dependency in core logic
- adapter pattern required
