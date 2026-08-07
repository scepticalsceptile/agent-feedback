# Source Code Phase 1

## Objective

Build the foundational public models and package surface without implementing
the loop yet.

## Scope

Create the core types that everything else depends on:

- `Request`
- `RetryableFailure`
- `TerminalFailure`
- `Attempt`
- `AttemptHistory`
- `RunResult`
- public exports from `agent_feedback.__init__`

## Proposed modules

```text
src/agent_feedback/
    __init__.py
    _request.py
    _failures.py
    _history.py
    _result.py
```

## Key decisions to encode

- `Request.args` is stored as a tuple
- `Request.kwargs` is copied into a fresh dict on construction
- `RetryableFailure.feedback` is compulsory
- `RetryableFailure.apply_feedback` is optional override
- `AttemptHistory` is sequence-like, not a mutable state manager

## Tests unlocked in this phase

- request construction
- request envelope repr/equality behavior if needed
- failure object construction
- result/history object construction
- public API exports import correctly

## Out of scope

- callback invocation
- actual loop behavior
- helpers

## Phase acceptance criteria

- package can import the foundational models cleanly
- no loop code exists yet
- tests for models and exports pass
