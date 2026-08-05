# Source Code Phase 5A

## Objective

Add a reusable `Runner` convenience object for codebases that share one stable
`invoke(...)` path and often share default `extract(...)`, `validators`,
`apply_feedback`, or retry settings.

This phase should add ergonomics only. It should not add a second execution
model.

## Scope

Implement a public `Runner` object that stores reusable defaults and delegates
to the existing `arun(...)` and `arun_full(...)` functions.

### Constructor shape

- `invoke` is required
- `extract` optional default
- `validators` optional default
- `apply_feedback` optional default
- `on_exhausted_retries` optional default for `Runner.arun(...)`
- `max_attempts` optional default
- no `request` on the constructor

### Method shape

Expose both:

- `Runner.arun(...)`
- `Runner.arun_full(...)`

Method rules:

- `request` is required per call
- methods do not accept `invoke=`
- per-call arguments override runner defaults for that call
- `validators=` replaces rather than merges
- `Runner.arun_full(...)` remains unaffected by
  `on_exhausted_retries`, just like the function form

## Important implementation constraint

This object needs a clean distinction between:

- omitted argument: use the runner default
- explicit override: replace the runner default for this call

That means implementation will likely need an internal sentinel rather than
using `None` or `()` directly as method defaults.

Examples where that distinction matters:

- explicit `validators=()` should be able to disable runner-level validators
- explicit `apply_feedback=None` should be able to disable runner-level
  `apply_feedback`

## Recommended shape

Prefer an immutable public object, such as a frozen dataclass or an equivalent
slots-based class.

The runner should be safe to keep at module scope and reuse across a codebase.

## Proposed modules

```text
src/agent_feedback/
    _runner.py
    __init__.py
tests/
    test_runner_object.py
```

No new execution module is required. The runner object should sit beside the
existing function entry points.

## Tests unlocked in this phase

- runner uses constructor defaults when method overrides are omitted
- local `extract=` overrides runner default
- local `validators=` replaces runner default
- local `apply_feedback=` overrides runner default
- runner-level `on_exhausted_retries` applies to `Runner.arun(...)`
- runner-level `max_attempts` applies when omitted per call
- `Runner.arun_full(...)` delegates to the structured result path
- explicit `validators=()` can disable runner validators
- explicit `apply_feedback=None` can disable runner default feedback behavior

## Out of scope

- singleton management
- mutable runtime reconfiguration of one runner instance
- merging validator lists automatically
- helper families

## Phase acceptance criteria

- `Runner` introduces no new loop semantics
- the same inputs produce the same outcomes as the function API
- override behavior is explicit and predictable
- the object is reusable enough for module-level shared configuration