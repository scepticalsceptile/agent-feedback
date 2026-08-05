# Source Code Phase 5

## Objective

Add the first-party helper layer carefully, without introducing framework
dependencies or dishonest magic.

## Scope

Implement only helpers that can stay zero-dependency and truthful about the
request family they operate on.

### Bare-request helper family

Candidates:

- `append_feedback_text(...)`
- `retry_same_request()` only if it can coexist cleanly with the non-mutation
  contract
- other string or sequence helpers that do not assume a provider SDK

### `Request(...)` helper family

Candidates:

- `replace_arg(index=0, ...)`
- `replace_kwarg(name="input", ...)`
- `append_message_kwarg(name="messages", ...)`

## Important constraint

The package has zero runtime dependencies.

That means helper design must not import LangChain message classes or any other
external SDK types. If a helper name implies a framework-specific object model,
either redesign it around pure Python values or leave it out of v1.

## Proposed modules

```text
src/agent_feedback/
    helpers.py
```

If the helper surface grows, it can later be split internally while preserving
one public helpers module.

## Tests unlocked in this phase

- helpers return fresh objects
- helpers do not mutate prior request values
- `Request(...)` helpers preserve untouched args and kwargs
- helper outputs can be fed directly into the next attempt

## Out of scope

- framework-specific helper adapters
- extra convenience layers that hide which part of the request they mutate

## Phase acceptance criteria

- helper functions are dependency-free
- helper behavior is explicit and predictable
- helper tests prove no in-place mutation of the outer request container
