# Source Code Phase 3

## Objective

Implement the real async loop in `arun_full(...)`.

## Scope

This phase builds the core behavior:

- invoke
- extract
- validate
- resolve `apply_feedback`
- retry until success, exhaustion, or terminal failure
- record `AttemptHistory`
- return `RunResult`

## Proposed modules

```text
src/agent_feedback/
    _runner.py
```

## Key decisions to encode

- `RetryableFailure.apply_feedback` overrides run-level `apply_feedback`
- if neither apply-feedback path exists, raise configuration error
- uncaught exceptions propagate unchanged
- `Attempt.raw_output` stores exact invoke return value
- `Attempt.output` stores extracted output
- history is an audit trail, not a mutable state machine

## Tests unlocked in this phase

- succeeds first try
- succeeds after multiple attempts
- exhaustion result in `arun_full(...)`
- invoke-level `RetryableFailure`
- extractor-level `RetryableFailure`
- validator-level `RetryableFailure`
- `TerminalFailure` stop behavior
- uncaught exception propagation
- history content and ordering

## Out of scope

- `arun(...)` convenience behavior
- helper families

## Phase acceptance criteria

- `arun_full(...)` matches the design doc semantics
- all core loop outcome tests pass
- history objects contain the expected request/raw_output/output/failure data
- `RunResult` exposes the final attempt request as `last_request`
