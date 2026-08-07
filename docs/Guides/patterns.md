# Patterns

This guide collects the reusable patterns that sit on top of the core loop.
These are userland recipes built from the public API, not hidden framework
machinery.

## Reuse one pipeline with `Runner`

If many call sites share the same invoke function, extractor, validators, or
feedback behavior, package those defaults once.

```python
from agent_feedback import RetryableFailure, Runner


def require_tool_call(response) -> None:
    if not response.tool_calls:
        raise RetryableFailure(
            "Model did not call a tool.",
            feedback="You must call a tool for this task.",
        )


runner = Runner(
    invoke=model.ainvoke,
    extract=lambda response: response,
    validators=[require_tool_call],
    apply_feedback=lambda feedback, previous_request: previous_request + [
        {"role": "system", "content": feedback}
    ],
    max_attempts=3,
)

first = await runner.arun(request=messages_a)
second = await runner.arun(request=messages_b)
```

This keeps the retry policy consistent across call sites without introducing a
new orchestration layer.

## Use request-shaped feedback functions

`apply_feedback(...)` is not universal because request shapes are not universal.
Write feedback functions that match the request family you actually use.

### Plain string prompt

```python
apply_feedback=lambda feedback, previous_request: f"{previous_request}\n\n{feedback}"
```

### Message list

```python
apply_feedback=lambda feedback, previous_request: previous_request + [
    {"role": "system", "content": feedback}
]
```

### `Request(...)` envelope

```python
from agent_feedback import Request


def add_system_feedback(feedback: str, previous_request: Request) -> Request:
    previous_messages = previous_request.kwargs["messages"]
    next_messages = previous_messages + [{"role": "system", "content": feedback}]
    next_kwargs = dict(previous_request.kwargs)
    next_kwargs["messages"] = next_messages
    return Request(*previous_request.args, **next_kwargs)
```

Always return a fresh value. Do not mutate the previous request in place.

## Escalate feedback using history

Sometimes the right retry strategy changes after repeated failures. `history`
lets `apply_feedback(...)` make later retries more explicit without changing
your validators.

In `apply_feedback(...)`, `history` already includes the failed attempt that
triggered the retry. That makes `len(history)` a useful "how many failures so
far?" counter.

```python
def escalate_feedback(feedback, previous_request, error, history):
    failed_attempts = len(history)

    if failed_attempts == 1:
        prefix = "Fix the problem described below."
    else:
        prefix = (
            f"This has already failed {failed_attempts} times. "
            "Fix the exact issue below."
        )

    return previous_request + [
        {
            "role": "system",
            "content": f"{prefix}\n\nReason: {error.message}\n\n{feedback}",
        }
    ]
```

Use this pattern when the first retry can be gentle, but later retries should
be sharper or more specific.

## Raise `RetryableFailure` from anywhere in the loop

Failures do not have to come from validators.

### From `invoke(...)`

```python
from agent_feedback import RetryableFailure


async def invoke_with_schema_check(request):
    response = await model.ainvoke(request)
    if not response.tool_calls:
        raise RetryableFailure(
            "The provider response did not contain a tool call.",
            feedback="You must answer by calling a tool.",
        )
    return response
```

### From `extract(...)`

```python
from agent_feedback import RetryableFailure


def extract_tool_call(response):
    if not response.tool_calls:
        raise RetryableFailure(
            "No tool call was present.",
            feedback="Return a tool call instead of plain text.",
        )
    return response.tool_calls[0]
```

This is useful when the problem is really about parsing or provider response
shape, not business validation.

## Wrap exceptions with a decorator

If an existing function already throws useful exceptions, you can wrap those
exceptions and turn them into retryable failures.

```python
import functools
import inspect

from agent_feedback import RetryableFailure


def retryable(*, catch=(Exception,), feedback_from_error=str):
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except catch as exc:
                    raise RetryableFailure(
                        str(exc),
                        feedback=feedback_from_error(exc),
                    ) from exc

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch as exc:
                raise RetryableFailure(
                    str(exc),
                    feedback=feedback_from_error(exc),
                ) from exc

        return sync_wrapper

    return decorator
```

Usage:

```python
@retryable(catch=(ValueError,))
async def invoke_with_parsing(request):
    return await model.ainvoke(request)
```

This is a userland pattern. The core package does not ship a built-in decorator.

## Use validators as deterministic eval hooks

Validators are already judging the output. That makes them useful observation
points even when they never fail.

```python
def record_quality(output, history) -> None:
    metrics.log(
        "reply_length",
        len(output),
        extra={"attempts_so_far": len(history)},
    )
```

Attach validators like that anywhere you want pass/fail or quality telemetry.
Just remember the rule: success means returning `None`, not `True` or `False`.

## Shape the extractor to the provider

The loop stays the same across SDKs. The main thing that changes is how you
extract the validation subject.

```python
# OpenAI Responses API
extract=lambda response: response.output_text

# Anthropic Messages API
extract=lambda response: response.content

# LangChain chat model
extract=lambda response: response.tool_calls
```

Keep the loop generic and let the extractor adapt to the provider object.

## Know when not to use the loop

`agent-feedback` is deliberately narrow. It is usually the wrong tool for:

- streaming token-by-token workflows
- batch orchestration
- generic transport retry on network or auth failures
- situations where retrying should happen without changing the request

In those cases, keep the concern separate and layer `agent-feedback` only where
application-level validation and feedback are actually the problem.

## Related docs

- [Getting Started](./getting_started.md)
- [API Reference](./api_reference.md)