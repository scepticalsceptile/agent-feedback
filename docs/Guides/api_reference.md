# API Reference

This document describes the public runtime contract of `agent-feedback` v1.
When behavior details matter, treat the implementation and tests as the source
of truth.

## Entry points

### `arun(...)`

```python
async def arun(
    *,
    request: Any,
    invoke: Callable[..., Any],
    extract: Callable[..., Any] = identity,
    validators: Sequence[Callable[..., Any]] = (),
    apply_feedback: ApplyFeedback | None = None,
    max_attempts: int = 3,
    on_exhausted_retries: Literal["raise", "return_last"] = "raise",
) -> Any
```

Behavior:

- Returns the extracted output on success.
- Raises `TerminalFailure` immediately if one is raised during the loop.
- Raises `ExhaustedRetriesError` when retries are exhausted, unless
  `on_exhausted_retries="return_last"` is set.
- Chains the final invoke, extract, or validator `RetryableFailure` as the
  raised error's `__cause__` so the original failure remains inspectable.
- Returns the final extracted output on retry exhaustion when
  `on_exhausted_retries="return_last"` is set.
- May return `None` in that exhaustion mode if the final attempt never produced
  extracted output.
- Propagates unexpected exceptions unchanged.

### `arun_full(...)`

```python
async def arun_full(
    *,
    request: Any,
    invoke: Callable[..., Any],
    extract: Callable[..., Any] = identity,
    validators: Sequence[Callable[..., Any]] = (),
    apply_feedback: ApplyFeedback | None = None,
    max_attempts: int = 3,
) -> RunResult
```

Behavior:

- Returns a `RunResult` on success, terminal failure, or retry exhaustion.
- Does not accept `on_exhausted_retries` because it already returns structured
  outcome information.
- Still raises configuration errors such as `MissingApplyFeedbackError`.
- Still propagates unexpected exceptions unchanged.

### `Runner`

```python
class Runner:
  def __init__(self, *, invoke: Callable[..., Any], extract: Callable[..., Any] = identity, validators: Sequence[Callable[..., Any]] = (), apply_feedback: ApplyFeedback | None = None, max_attempts: int = 3, on_exhausted_retries: Literal["raise", "return_last"] = "raise") -> None: ...
  async def arun(self, *, request: Any, ...) -> Any: ...
  async def arun_full(self, *, request: Any, ...) -> RunResult: ...
```

Behavior:

- `Runner` stores reusable defaults for the same underlying loop.
- `Runner.arun(...)` and `Runner.arun_full(...)` reuse those defaults unless a
  per-call override is supplied.
- Explicit override values can disable runner defaults.
- For example, `apply_feedback=None` disables a runner-level feedback strategy,
  and `validators=()` disables runner-level validators.

## Pipeline function contracts

The loop has four functional stages:

1. `invoke`
2. `extract`
3. `validator`
4. `apply_feedback`

The harness does not treat all four the same.

- `invoke` is chosen by request family, not callback arity overloads.
- `extract`, `validator`, and `apply_feedback` use explicit, runtime-supported
  positional shapes.
- `RetryableFailure` and `TerminalFailure` can be raised from any stage.

### `invoke`

`invoke` is your existing callable. The harness does not add its own overloads
to `invoke`; it simply calls it according to the request family.

Supported invocation forms:

- bare request: `await invoke(request)`
- explicit envelope: `await invoke(*request.args, **request.kwargs)`

Use a bare request when your invoke callable naturally takes one argument. Use
`Request(...)` when the invoke callable expects exact positional and keyword
arguments.

## Request families

### Bare request

If you pass a normal request object, the harness calls:

```python
await invoke(request)
```

Examples:

```python
request=messages
request=prompt
request=my_request_object
```

### `Request(...)` envelope

Use `Request(...)` when the invoke callable expects exact positional and keyword
arguments.

```python
from agent_feedback import Request


request = Request("hello", model="gpt-5.5")
```

The harness calls:

```python
await invoke(*request.args, **request.kwargs)
```

Properties:

- `args: tuple[Any, ...]`
- `kwargs: dict[str, Any]`

`apply_feedback(...)` sees the same request family that was passed for that
attempt. Bare requests stay bare. `Request(...)` stays wrapped. In examples,
it is often clearer to name that parameter `previous_request`.

### `extract`

The extractor chooses what should be validated and what `arun(...)` should
return on success.

```python
extract(response)
extract(response, request)
extract(response, request, history)
```

Use:

- `extract(response)` when the raw response is enough.
- `extract(response, request)` when extraction depends on the original request.
- `extract(response, request, history)` when extraction depends on earlier
  attempts.

### `validator`

Validators accept or reject the extracted output.

```python
validator(output)
validator(output, history)
```

Use:

- `validator(output)` for simple acceptance checks.
- `validator(output, history)` when the rule depends on previous attempts.

Validators must return `None` on success. Failures must be signaled by raising
`RetryableFailure` or `TerminalFailure`.

### `apply_feedback`

`apply_feedback(...)` builds the next request after a retryable failure.
`previous_request` is the exact request object from the failed attempt.

```python
apply_feedback(feedback, previous_request)
apply_feedback(feedback, previous_request, error)
apply_feedback(feedback, previous_request, error, history)
```

Use:

- `apply_feedback(feedback, previous_request)` for static request rewriting.
- `apply_feedback(feedback, previous_request, error)` when the next request depends on
  the specific failure.
- `apply_feedback(feedback, previous_request, error, history)` when the next request
  depends on both the failure and prior attempts.

### Dispatch rules for callback shapes

The callback shapes are intentionally small and explicit. You can think of
them as runtime-supported callback overloads: the harness inspects how many
positional parameters your function accepts, then calls it with the matching
shape.

Start with the smallest shape that works and add more parameters only when you
need more context.

Rules:

- The harness dispatches by supported positional arity.
- Supported arities are `1, 2, 3` for `extract`, `1, 2` for `validator`, and
  `2, 3, 4` for `apply_feedback`.
- Each callback may be sync or async.
- Unsupported shapes raise `TypeError`.
- `*args` are not supported.
- Required keyword-only parameters are not supported.
- Only the documented positional arguments are supplied by the harness.
- Callbacks are inspected at runtime; unsupported shapes raise `TypeError`.

## Failure types

### `RetryableFailure`

```python
class RetryableFailure(Exception):
    def __init__(
        self,
        message: str,
        *,
        feedback: Any,
        apply_feedback: ApplyFeedback | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...
```

Semantics:

- Signals that the loop should retry if attempts remain.
- `feedback` is required.
- `apply_feedback` is an optional per-failure override.
- `metadata` is stored on the exception, but the core harness does not
  interpret it.

### `TerminalFailure`

```python
class TerminalFailure(Exception):
    def __init__(self, message: str) -> None: ...
```

Semantics:

- Signals that the loop should stop immediately.
- `arun(...)` raises it.
- `arun_full(...)` returns it inside `RunResult.final_failure`.

### `ExhaustedRetriesError`

```python
class ExhaustedRetriesError(AgentFeedbackError):
  def __init__(self, *, attempts: int, last_failure: RetryableFailure) -> None: ...
```

Semantics:

- Raised by `arun(...)` and `Runner.arun(...)` when the retry budget is exhausted.
- `attempts` records how many attempts were consumed.
- `last_failure` exposes the original final `RetryableFailure`.
- The original `RetryableFailure` is also attached as `__cause__`.

### Retry-path resolution order

When a `RetryableFailure` occurs, the next-request strategy is resolved in this
order:

1. `failure.apply_feedback`
2. run-level `apply_feedback=` argument

If neither exists, the harness raises `MissingApplyFeedbackError`.

There is no default "retry the same request" behavior.

## Where failures can come from

`RetryableFailure` and `TerminalFailure` may be raised from:

- the invoke callable
- the extractor
- any validator

The loop handles them the same way regardless of where they originate.

Unexpected exceptions are different. They propagate unchanged unless you catch
and re-raise them yourself as `RetryableFailure` or `TerminalFailure`.

## History and result models

### `Attempt`

```python
@dataclass(frozen=True, slots=True)
class Attempt:
    request: Any
    raw_output: Any | None
    output: Any | None
    failure: Exception | None
    attempt_number: int
```

Each attempt records the request that was tried, the raw invoke output, the
extracted output, the failure if one occurred, and the one-based attempt number.

### `AttemptHistory`

```python
@dataclass(frozen=True, init=False, slots=True)
class AttemptHistory(Sequence[Attempt]):
    max_attempts: int
    attempts: tuple[Attempt, ...]

    @property
    def last_attempt(self) -> Attempt | None: ...
```

Semantics:

- Immutable and sequence-like.
- Supports indexing and slicing.
- Exposes `last_attempt` for convenience.
- Exists for advanced logic and observability, not as a mutable state machine.

### `RunResult`

```python
@dataclass(frozen=True, slots=True)
class RunResult:
    output: Any | None
    raw_output: Any | None
    last_request: Any
    history: AttemptHistory
    final_failure: Exception | None
    exhausted: bool
```

Fields:

- `output`: final extracted output, if one exists
- `raw_output`: final raw invoke result, if one exists
- `last_request`: the last request that was actually attempted
- `history`: immutable attempt history
- `final_failure`: `None`, `RetryableFailure`, or `TerminalFailure`
- `exhausted`: whether retries ended because the attempt budget ran out

## Configuration and library-defined errors

### `MissingApplyFeedbackError`

```python
class MissingApplyFeedbackError(AgentFeedbackError):
    ...
```

Raised when a retryable failure occurs but the harness cannot find any
`apply_feedback` path.

### `AgentFeedbackError`

```python
class AgentFeedbackError(Exception):
    ...
```

Base class for library-defined exceptions.

### Other errors

- `ValueError` is raised if `max_attempts < 1`.
- `TypeError` is raised for unsupported callback signatures or validators that
  return a non-`None` value.
- Unexpected exceptions propagate unchanged.

## Practical rules

- Return fresh request values from `apply_feedback(...)`.
- Do not mutate old requests, outputs, or history entries in place.
- Use `arun(...)` when you only need the final extracted output.
- Use `arun_full(...)` when you need diagnostics or attempt history.
- Use `Runner` only after you see repeated loop configuration across call sites.
