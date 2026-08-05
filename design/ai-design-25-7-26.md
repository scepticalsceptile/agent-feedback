# AI Design 25-7-26

This is the current v1 direction for the harness.

The goal is a small, framework-agnostic feedback loop around any LLM
invocation callable. The harness should do only four things:

1. invoke
2. extract
3. validate
4. retry on controlled failure

## Happy path

```python
result = await arun(
	invoke=model.ainvoke,
	request=messages,
	extract=lambda response, request: response,
	validators=[require_tool_call],
	apply_feedback=append_feedback_message(role="system"),
	max_attempts=3,
)
```

The simple path should feel like "wrap what I already do" rather than "learn a
new framework."

## Core decisions

- This document is async-first. A sync wrapper can mirror the same model later.
- `RetryableFailure` may be raised from `invoke`, `extract`, or validators.
- `RetryableFailure` owns the feedback payload for the next attempt.
- A bare request stays bare for user callbacks.
- An explicit `Request(...)` stays wrapped for user callbacks.
- The harness may normalize requests internally for invocation, but that is
  hidden from user callbacks.
- Default return is extracted output only. A separate full-result entry point
  returns history and diagnostics.

## Public API

```python
async def arun(
	*,
	invoke: Callable[..., Any],
	request: Any,
	extract: Extractor = identity,
	validators: Sequence[Validator] = (),
	apply_feedback: ApplyFeedback | None = None,
	on_exhausted_retries: Literal["raise", "return_last"] = "raise",
	max_attempts: int = 3,
) -> Any:
	...


async def arun_full(
	*,
	invoke: Callable[..., Any],
	request: Any,
	extract: Extractor = identity,
	validators: Sequence[Validator] = (),
	apply_feedback: ApplyFeedback | None = None,
	max_attempts: int = 3,
) -> RunResult:
	...
```

`arun(...)` is the normal entry point and returns the extracted output.

On success, `arun(...)` returns the extracted output.

If a `TerminalFailure` occurs, `arun(...)` raises it.

If retries are exhausted after a `RetryableFailure`, `arun(...)` raises the
final failure by default. If `on_exhausted_retries="return_last"`, it returns
the last extracted output from the final attempt instead. That value may be
`None` if the final attempt never produced an extracted output.

`arun_full(...)` returns a richer result object containing output, raw output,
the last request that was actually attempted, history, and the final failure if
retries stop.

`arun_full(...)` returns a `RunResult` for the normal loop outcomes and does
not use `on_exhausted_retries`.

Configuration errors, such as a `RetryableFailure` with no available
`apply_feedback` path, still raise. Unexpected exceptions also propagate
unchanged.

### Reusable `Runner` convenience object

For codebases where `invoke`, `extract`, or `apply_feedback` are usually
shared, the package may also expose a small reusable `Runner` object.

The constructor should mirror the defaultable parts of `arun(...)`, with one
important change: `invoke=` is required and `request=` is not stored on the
runner.

`Runner.arun(...)` and `Runner.arun_full(...)` should mirror the function
entry points, except `invoke=` is fixed on the runner and `request=` remains
required per call.

Example:

```python
runner = Runner(
	invoke=agent.invoke,
	extract=global_extractor,
	apply_feedback=global_feedback,
	max_attempts=3,
)

result = await runner.arun(
	request=messages,
	extract=local_extractor,
)
```

Rules:

- `invoke` is required at construction time.
- `request` is required per call.
- `Runner.arun(...)` and `Runner.arun_full(...)` do not accept `invoke=`.
- omitted call arguments use runner defaults.
- supplied call arguments override runner defaults for that call.
- `validators=` replaces the runner default rather than merging with it.
- `Runner` is additive convenience only; it should delegate to the same core
  behavior as `arun(...)` and `arun_full(...)` rather than introducing a new
  execution model.
- users may keep one module-level `Runner` and reuse it widely, but the core
  package should not require singleton semantics.

## Request model

There are two public request families.

### 1. Bare request

This is the common path.

Examples:

```python
request=messages
request=prompt
request=my_request_object
```

Invocation rule:

```python
await invoke(request)
```

Ergonomic rule:

If the user passed `request=messages`, then `apply_feedback(feedback, request, ...)`
receives the same messages object shape, not an internal wrapper.

### 2. Explicit call envelope

This is the escape hatch for exact call signatures.

```python
class Request:
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		self.args = tuple(args)
		self.kwargs = dict(kwargs)
```

Examples:

```python
Request(messages)
Request(input="Hi", model="gpt-5.5")
Request(messages, schema=Cat)
```

Invocation rule:

```python
await invoke(*request.args, **request.kwargs)
```

Ergonomic rule:

If the user passed `request=Request(...)`, then
`apply_feedback(feedback, request, ...)` receives that same `Request` envelope.

### Internal normalization

The harness may internally normalize requests into a call envelope right before
invocation, but that normalization is private.

User callbacks should see the request shape that the user actually passed for
that attempt.

An `apply_feedback` callable may return either another bare request or a
`Request(...)` envelope. The harness re-normalizes on every attempt.

### Immutability rule

Requests should be treated as immutable.

`apply_feedback` callables should return a fresh request value or a fresh
`Request(...)` envelope. The harness records each returned request separately,
but it should not promise deep copies of arbitrary user objects.

This is a correctness requirement for history, not just a style preference.

- `invoke()` should only inspect the request and return a fresh `raw_output`.
- `extract()` should only inspect its inputs and return a fresh `output`.
- validators should only inspect and either return None or raise.
- `apply_feedback()` should only inspect its inputs and return a fresh next
  request.
- the harness records references, not frozen deep snapshots.

If user callbacks mutate `request`, `raw_output`, `output`, or `history` in
place, old attempts in history may become misleading or corrupted.

For example, this is wrong:

```python
def my_feedback_appender(feedback, request):
	request.append(SystemMessage(feedback))
	return request
```

That mutates the same list object that may already be stored in history.

Return a fresh object instead:

```python
def my_feedback_appender(feedback, request):
	return request + [SystemMessage(feedback)]
```

This works because in Python, `list + list` creates a new list object rather than mutating the old one.

Even then, if nested mutable objects are shared and later mutated elsewhere,
history can still drift. The harness does not deep-copy arbitrary request
graphs.

## Supported callback shapes

The harness should support a small, explicit set of callback shapes and reject
unsupported ones with a clear error.

Extractor:

```python
extract(response)
extract(response, request)
extract(response, request, history)
```

Validator:

```python
validator(output)
validator(output, history)
```

Apply feedback:

```python
apply_feedback(feedback, request)
apply_feedback(feedback, request, error)
apply_feedback(feedback, request, error, history)
```

This is intentionally loose at the typing level. The users are writing these
functions, so runtime normalization plus clear errors is more useful than a
Protocol-heavy public surface.

Each supported callback shape may be sync or async. The harness should call the
function and await the result only when it is awaitable.

Validators must return `None` on success. Any other return value, including
`False`, should be treated as a `TypeError`; failures must be signaled by
raising `RetryableFailure` or `TerminalFailure`.

## Controlled failures

```python
class RetryableFailure(Exception):
	def __init__(
		self,
		message: str,
		*,
		feedback: Any,
		apply_feedback: ApplyFeedback | None = None,
		metadata: dict[str, Any] | None = None,
	) -> None:
		...


class TerminalFailure(Exception):
	...
```

Rules:

- `RetryableFailure` means retry if attempts remain.
- `TerminalFailure` means stop immediately.
- `RetryableFailure.feedback` is compulsory.
- `RetryableFailure.apply_feedback` overrides the run-level
	`apply_feedback=` argument.
- The run-level `apply_feedback=` argument is the fallback for reusable
	validators.
- Reusable validators generally should provide `feedback`, but not
	`apply_feedback`; the call site usually supplies the request-family-specific
	apply-feedback behavior.
- If a retryable failure occurs and neither apply-feedback path exists, that is
	a configuration error.
- There is no default "retry the same request" behavior.
- Unexpected exceptions propagate by default.
- An uncaught provider or structured-output exception does not retry unless the
	user deliberately wraps or re-raises it as `RetryableFailure` or
	`TerminalFailure`.
- The core harness does not interpret `metadata`; request-family-specific
	`apply_feedback` helpers may inspect it if they want to.

## History and result

`AttemptHistory` is an immutable audit trail, not the pipeline brain.

```python
@dataclass(frozen=True)
class Attempt:
	request: Any
	raw_output: Any | None  # exact value returned by invoke()
	output: Any | None  # extracted value returned by extract()
	failure: Exception | None
	attempt_number: int


class AttemptHistory(Sequence[Attempt]):
	max_attempts: int

	@property
	def last_attempt(self) -> Attempt | None:
		...
```

`AttemptHistory` exists for advanced extract/retry logic and observability. Most
users should not need it.

```python
@dataclass(frozen=True)
class RunResult:
	output: Any | None
	raw_output: Any | None
	last_request: Any
	history: AttemptHistory
	final_failure: Exception | None
	exhausted: bool
```

## Loop semantics

1. invoke the current request
2. extract the validation subject
3. run validators in order
4. return on success
5. if `RetryableFailure` is raised anywhere, resolve how feedback will be
	applied
6. build the next request from `error.feedback` and retry
7. stop on `TerminalFailure` or retry exhaustion

The apply-feedback resolution order is:

1. `failure.apply_feedback`
2. call-level `apply_feedback=`

## Helper families

Helpers should be explicit about the request family they operate on.

These helpers produce `apply_feedback` callables.

Bare-request helpers:

- `append_feedback_text(...)`
- `append_feedback_message(...)`
- `retry_same_request()`

`Request(...)` helpers:

- `replace_arg(index=0, ...)`
- `replace_kwarg(name="input", ...)`
- `append_message_kwarg(name="messages", ...)`

Helpers are narrow convenience wrappers around the same retry seam. They should
not pretend to be universal.

## Examples

### Bare request

```python
result = await arun(
	invoke=model.ainvoke,
	request=messages,
	extract=lambda response, request: response,
	validators=[require_tool_call],
	apply_feedback=append_feedback_message(role="system"),
	max_attempts=3,
)
```

### Explicit call envelope

```python
result = await arun(
	invoke=client.responses.create,
	request=Request(
		input="Hi! Who are you?",
		model="gpt-5.5",
		instructions="You are a helpful assistant",
	),
	extract=lambda response, request: response.output_text,
	validators=[must_be_json],
	apply_feedback=replace_kwarg(
		name="input",
		transform=lambda previous, feedback: f"{previous}\n\n{feedback}",
	),
	max_attempts=3,
)
```

### Reusable runner

```python
runner = Runner(
	invoke=model.ainvoke,
	extract=lambda response, request: response,
	apply_feedback=append_feedback_message(role="system"),
	max_attempts=3,
)

result = await runner.arun(
	request=messages,
	validators=[require_tool_call],
)
```

### Retryable failure raised from `invoke(...)`

```python
async def invoke(request: Request):
	try:
		return await client.responses.create(*request.args, **request.kwargs)
	except StructuredOutputError as exc:
		raise RetryableFailure(
			"Structured output did not match the schema.",
			feedback="Return output that matches the requested schema exactly.",
			apply_feedback=replace_kwarg(
				name="input",
				transform=lambda previous, feedback: f"{previous}\n\n{feedback}",
			),
		) from exc
```

This is allowed, but the normal teaching path should still be: derive output in
`extract(...)`, validate in validators, and keep advanced wrappers rare.

## Non-goals for v1

- streaming support
- batch orchestration
- provider-specific adapters in the core package
- broad exception-catching retries for transport/auth/programming errors
- turning `AttemptHistory` into a lifecycle framework
- magical helpers that infer what part of a request should change
