# Source Code Phase 6

## Objective

Improve the public typing story without pretending the harness can infer type
information that the caller or upstream SDK never supplied.

This phase should increase editor help and type-checker usefulness while
preserving the current runtime behavior and callback ergonomics.

## Scope

Add "good enough" typing to the current API surface:

- preserve request, raw-output, and extracted-output types through the run
- make `Attempt`, `AttemptHistory`, and `RunResult` generic again
- add typed callback families for extractors and validators
- add overloads for `arun(...)` and `arun_full(...)`
- keep the bare-request path as the strongly typed happy path
- keep `Request(...)` as a dynamic escape hatch rather than overfitting to
  `ParamSpec` complexity in v1

## Key decisions to encode

- The real type pipeline is still three values: request, raw output, extracted
  output.
- Strong typing only works when upstream types exist. If `invoke(...)` returns
  `Any`, the harness cannot recover lost type information.
- The response-first extractor contract should be reflected in the type
  aliases and overloads.
- The explicit `Request(...)` envelope should stay lightly typed because it
  exists specifically for arbitrary call shapes.
- `RetryableFailure.feedback` and `metadata` should remain loosely typed in v1.
- This phase should not change runtime behavior.

## Important caveat

Static typing is sharpest when the request family stays stable across retries.

If a user starts with one request type and their `apply_feedback(...)` returns
a different request family later, the best type story will necessarily widen to
a union or `Any`.

That is acceptable. The harness should preserve honest typing, not fake
precision.

## Proposed modules

```text
src/agent_feedback/
    _typing.py
    _history.py
    _result.py
    _runner.py
    _callbacks.py
```

No new public runtime module is required. The intent is to centralize typing
aliases and protocols privately, then thread those generics through the
existing public objects and entry points.

## Recommended type shape

### Core type variables

Use the same three-type core that was directionally right in the older design
draft:

```python
TRequest = TypeVar("TRequest")
TRawOutput = TypeVar("TRawOutput")
TOutput = TypeVar("TOutput")
```

This is the strongest honest claim the harness can make:

- `TRequest` is the request type for one attempt
- `TRawOutput` is the exact return type of `invoke(...)`
- `TOutput` is the extracted value validators receive and `arun(...)` returns

### Async-or-sync helper

```python
T = TypeVar("T")
MaybeAwaitable = T | Awaitable[T]
```

This lets the public callable aliases stay faithful to the current API choice
that invoke, extract, validators, and apply-feedback may be sync or async.

## Typing sketch

The sketch below is intentionally aligned with the current API, not the older
defunct context-object design.

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeAlias, TypeVar, overload

TRequest = TypeVar("TRequest")
TRawOutput = TypeVar("TRawOutput")
TOutput = TypeVar("TOutput")
T = TypeVar("T")

MaybeAwaitable: TypeAlias = T | Awaitable[T]


class ExtractResponseOnly(Protocol[TRawOutput, TOutput]):
    def __call__(self, response: TRawOutput, /) -> MaybeAwaitable[TOutput]: ...


class ExtractResponseRequest(Protocol[TRequest, TRawOutput, TOutput]):
    def __call__(
        self,
        response: TRawOutput,
        request: TRequest,
        /,
    ) -> MaybeAwaitable[TOutput]: ...


class ExtractResponseRequestHistory(Protocol[TRequest, TRawOutput, TOutput]):
    def __call__(
        self,
        response: TRawOutput,
        request: TRequest,
        history: AttemptHistory[TRequest, TRawOutput, TOutput],
        /,
    ) -> MaybeAwaitable[TOutput]: ...


Extractor: TypeAlias = (
    ExtractResponseOnly[TRawOutput, TOutput]
    | ExtractResponseRequest[TRequest, TRawOutput, TOutput]
    | ExtractResponseRequestHistory[TRequest, TRawOutput, TOutput]
)


class ValidatorOutputOnly(Protocol[TOutput]):
    def __call__(self, output: TOutput, /) -> MaybeAwaitable[None]: ...


class ValidatorOutputHistory(Protocol[TRequest, TRawOutput, TOutput]):
    def __call__(
        self,
        output: TOutput,
        history: AttemptHistory[TRequest, TRawOutput, TOutput],
        /,
    ) -> MaybeAwaitable[None]: ...


Validator: TypeAlias = (
    ValidatorOutputOnly[TOutput]
    | ValidatorOutputHistory[TRequest, TRawOutput, TOutput]
)


class ApplyFeedback2(Protocol[TRequest]):
    def __call__(self, feedback: Any, request: TRequest, /) -> MaybeAwaitable[TRequest]: ...


class ApplyFeedback3(Protocol[TRequest]):
    def __call__(
        self,
        feedback: Any,
        request: TRequest,
        error: RetryableFailure,
        /,
    ) -> MaybeAwaitable[TRequest]: ...


class ApplyFeedback4(Protocol[TRequest, TRawOutput, TOutput]):
    def __call__(
        self,
        feedback: Any,
        request: TRequest,
        error: RetryableFailure,
        history: AttemptHistory[TRequest, TRawOutput, TOutput],
        /,
    ) -> MaybeAwaitable[TRequest]: ...


ApplyFeedback: TypeAlias = (
    ApplyFeedback2[TRequest]
    | ApplyFeedback3[TRequest]
    | ApplyFeedback4[TRequest, TRawOutput, TOutput]
)


@dataclass(frozen=True, slots=True)
class Attempt(Generic[TRequest, TRawOutput, TOutput]):
    request: TRequest
    raw_output: TRawOutput | None
    output: TOutput | None
    failure: Exception | None
    attempt_number: int


class AttemptHistory(Sequence[Attempt[TRequest, TRawOutput, TOutput]]):
    ...


@dataclass(frozen=True, slots=True)
class RunResult(Generic[TRequest, TRawOutput, TOutput]):
    output: TOutput | None
    raw_output: TRawOutput | None
    last_request: TRequest
    history: AttemptHistory[TRequest, TRawOutput, TOutput]
    final_failure: Exception | None
    exhausted: bool


@overload
async def arun_full(
    *,
    invoke: Callable[[TRequest], MaybeAwaitable[TRawOutput]],
    request: TRequest,
    validators: Sequence[Validator[TRequest, TRawOutput, TRawOutput]] = (),
    apply_feedback: ApplyFeedback[TRequest, TRawOutput, TRawOutput] | None = None,
    max_attempts: int = 3,
) -> RunResult[TRequest, TRawOutput, TRawOutput]: ...


@overload
async def arun_full(
    *,
    invoke: Callable[[TRequest], MaybeAwaitable[TRawOutput]],
    request: TRequest,
    extract: Extractor[TRequest, TRawOutput, TOutput],
    validators: Sequence[Validator[TRequest, TRawOutput, TOutput]] = (),
    apply_feedback: ApplyFeedback[TRequest, TRawOutput, TOutput] | None = None,
    max_attempts: int = 3,
) -> RunResult[TRequest, TRawOutput, TOutput]: ...


@overload
async def arun(
    *,
    invoke: Callable[[TRequest], MaybeAwaitable[TRawOutput]],
    request: TRequest,
    validators: Sequence[Validator[TRequest, TRawOutput, TRawOutput]] = (),
    apply_feedback: ApplyFeedback[TRequest, TRawOutput, TRawOutput] | None = None,
    on_exhausted_retries: Literal["raise", "return_last"] = "raise",
    max_attempts: int = 3,
) -> TRawOutput: ...


@overload
async def arun(
    *,
    invoke: Callable[[TRequest], MaybeAwaitable[TRawOutput]],
    request: TRequest,
    extract: Extractor[TRequest, TRawOutput, TOutput],
    validators: Sequence[Validator[TRequest, TRawOutput, TOutput]] = (),
    apply_feedback: ApplyFeedback[TRequest, TRawOutput, TOutput] | None = None,
    on_exhausted_retries: Literal["raise", "return_last"] = "raise",
    max_attempts: int = 3,
) -> TOutput: ...
```

## How to treat `Request(...)`

Do not try to make `Request(...)` statically model arbitrary `*args` and
`**kwargs` in v1.

Recommended posture:

- keep `Request.args: tuple[Any, ...]`
- keep `Request.kwargs: dict[str, Any]`
- keep `invoke` broad for the explicit-envelope path
- document that the strongest typing story is the bare-request path with a
  typed wrapper function such as `invoke(request: MyRequest) -> MyProviderResponse`

This is a deliberate tradeoff. The explicit envelope exists for flexibility,
not because it can be typed beautifully.

## What this phase should improve for real users

If upstream callables are typed, this phase should make these scenarios much
better in editors and type checkers:

- a user can see the concrete response type inside `extract(...)`
- a validator can see the concrete extracted-output type
- `arun(...)` returns the extractor's output type rather than `Any`
- `RunResult.raw_output` exposes the provider response type
- `RunResult.last_request` and `Attempt.request` expose the request type
- history-aware extractors and validators can inspect typed attempts

## What this phase should not promise

- no automatic recovery of types from untyped SDKs that already return `Any`
- no full static modeling of arbitrary `Request(...)` call signatures
- no generic exception typing for `feedback` payloads or `metadata`
- no runtime behavior changes driven by typing
- no migration to a heavier context-object callback API just for better typing

## Suggested implementation order

1. add private typing aliases and protocols in `_typing.py`
2. make `Attempt`, `AttemptHistory`, and `RunResult` generic
3. thread generics through `_runner.py` and `_callbacks.py`
4. add overloads for `arun(...)` and `arun_full(...)`
5. keep `Request(...)` intentionally light rather than chasing `ParamSpec`
6. add type-check-focused fixtures or examples to exercise inferred types

## Tests unlocked in this phase

- mypy can confirm that a typed bare-request flow preserves response and output
  types end-to-end
- `arun(...)` returns `TRawOutput` when `extract` is omitted
- `arun(...)` returns `TOutput` when `extract` is present
- `RunResult.raw_output`, `RunResult.output`, and `RunResult.last_request`
  reveal expected types in typed examples
- history-aware extractor and validator examples receive typed `AttemptHistory`

These are primarily static-type validation checks, not new runtime behavior
tests.

## Out of scope

- sync wrapper design
- changing callback ergonomics to a single context-object protocol
- advanced `ParamSpec` or `TypeVarTuple` modeling for `Request(...)`
- framework-specific provider stubs or adapters
- type-driven debugging wrappers for user callback failures

## Phase acceptance criteria

- typed bare-request flows get useful editor inference for request, response,
  extracted output, and history
- `Attempt`, `AttemptHistory`, and `RunResult` carry honest generic types
- `arun(...)` and `arun_full(...)` use overloads that reflect the default
  extract path versus custom extract path
- `Request(...)` remains a documented dynamic escape hatch instead of a typing
  rabbit hole
- runtime behavior remains unchanged