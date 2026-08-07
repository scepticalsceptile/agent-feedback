# Source Code Phase 2

## Objective

Implement the internal callback and invocation utilities that make the loop
possible.

## Scope

Build the internal machinery for:

- calling sync or async user callbacks uniformly
- supporting the documented extractor arities
- supporting the documented validator arities
- supporting the documented `apply_feedback` arities
- normalizing invoke behavior for bare requests versus `Request(...)`
- rejecting invalid validator return values

## Proposed modules

```text
src/agent_feedback/
    _callbacks.py
    _invoke.py
```

## Key decisions to encode

- internal helper to await a result only when needed
- explicit supported callback shapes only
- clear `TypeError` for unsupported callback arity
- validator success means `None` only
- no signature-driven magic beyond what is required to support the documented
  callback forms

## Tests unlocked in this phase

- sync and async extractor variants
- sync and async validator variants
- sync and async `apply_feedback` variants
- invalid validator return type raises `TypeError`
- bare request invokes as one positional argument
- `Request(...)` invokes via `*args, **kwargs`

## Out of scope

- attempt loop
- exhaustion behavior
- helpers

## Phase acceptance criteria

- all documented callback shapes work
- invalid callback usage fails fast with readable errors
- invocation normalization is hidden from user callbacks
