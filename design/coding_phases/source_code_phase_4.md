# Source Code Phase 4

## Objective

Add the thin convenience API around the full runner.

## Scope

Implement `arun(...)` as a wrapper over `arun_full(...)` with explicit failure
behavior.

## Key decisions to encode

- on success, return extracted output
- on `TerminalFailure`, always raise
- on exhausted retries, default to raise the final failure
- if `on_exhausted_retries="return_last"`, return the final extracted output
  instead
- `arun_full(...)` remains the structured diagnostics entry point

## Proposed modules

No new major module is required if phase 3 already created a runner module.
This phase may extend `__init__.py` and `_runner.py` only.

## Tests unlocked in this phase

- `arun(...)` returns output on success
- `arun(...)` raises on terminal failure
- `arun(...)` raises on exhausted retries by default
- `arun(...)` returns last output with `return_last`
- `arun(...)` may return `None` with `return_last` when the final attempt never
  produced extracted output
- `arun_full(...)` remains unaffected by `on_exhausted_retries`

## Out of scope

- helper families

## Phase acceptance criteria

- `arun(...)` is now the normal public entry point
- convenience behavior is fully covered by tests
