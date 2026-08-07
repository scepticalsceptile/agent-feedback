# Getting Started

`agent-feedback` wraps an LLM invocation in a small loop:

1. call your existing invoke function
2. optionally extract the part you care about
3. validate it
4. give feedback and retry if needed

You keep your own SDK, your own request shape, and your own feedback strategy.
The library only runs the loop.

## Install

```bash
pip install agent-feedback
```

## Start with the smallest call

If your invoke function already returns the thing you want, the minimal case is
just `request` plus `invoke`:

```python
from agent_feedback import arun


result = await arun(
    request="Say hello in one short sentence.",
    invoke=model.ainvoke,
)
```

That calls `await model.ainvoke("Say hello in one short sentence.")` and
returns its output.

## Add extraction when your SDK returns a wrapper object

Most SDKs return response objects rather than bare strings. Use `extract(...)`
to choose what should be validated and returned.

```python
from agent_feedback import arun


result = await arun(
    request="Say hello in one short sentence.",
    invoke=model.ainvoke,
    extract=lambda response: response.output_text,
)
```

If your SDK uses `response.text`, `response.content`, `response.tool_calls`, or
something else, change the extractor accordingly. For more provider-shaped
examples, see [Shape the extractor to the provider](./patterns.md#shape-the-extractor-to-the-provider).

## Add validation and retry feedback

Validation failures are explicit. Your validator raises `RetryableFailure` and
includes the feedback that should help the next attempt.

```python
from agent_feedback import RetryableFailure, arun


def must_start_with_hello(text: str) -> None:
    if not text.lower().startswith("hello"):
        raise RetryableFailure(
            "The answer did not start with hello.",
            feedback="Start your answer with the word 'hello'.",
        )


result = await arun(
    request="Greet me in one short sentence.",
    invoke=model.ainvoke,
    extract=lambda response: response.output_text,
    validators=[must_start_with_hello],
    apply_feedback=lambda feedback, previous_request: f"{previous_request}\n\n{feedback}",
    max_attempts=3,
)
```

The flow is:

- `invoke` returns a raw response
- `extract` picks the validation subject
- each validator either returns `None` or raises
- `apply_feedback` builds the next request when a retryable failure happens

If you are wondering what those pipeline functions look like, the smallest
useful mental model is:

```python
invoke(request) -> raw_response
extract(raw_response) -> output
validator(output) -> None
apply_feedback(feedback, previous_request) -> next_request
```

Where:

- `request` is the original input you passed to `arun(...)`. See [invoke](./api_reference.md#invoke) and [request families](./api_reference.md#request-families).
- `raw_response` is whatever `invoke(...)` returned.
- `output` is what `extract(...)` returns and what `arun(...)` returns on success.
- `feedback` comes from `RetryableFailure(..., feedback=...)`. See [RetryableFailure](./api_reference.md#retryablefailure).
- `previous_request` is the exact request object from the failed attempt. If you passed `Request(...)`, this is that same `Request(...)` envelope. See [request families](./api_reference.md#request-families).
- `next_request` is whatever `apply_feedback(...)` returns for the retry.

The callback shapes are opt-in. Start with the smallest one that works, then
add parameters only when you need more context:

```python
extract(response)
extract(response, request)
extract(response, request, history)

validator(output)
validator(output, history)

apply_feedback(feedback, previous_request)
apply_feedback(feedback, previous_request, error)
apply_feedback(feedback, previous_request, error, history)
```

For example, use `request` in `extract(...)` when the response needs to be
interpreted relative to the original request, or use `history` in a validator
when the rule depends on earlier attempts. Each callback may be sync or async.
For the exact contract, see [Pipeline function contracts](./api_reference.md#pipeline-function-contracts) and [Dispatch rules for callback shapes](./api_reference.md#dispatch-rules-for-callback-shapes).

`apply_feedback(...)` is where many new users pause. It receives the retry
feedback plus the failed request and must return the next request to try. For
more examples, see [Use request-shaped feedback functions](./patterns.md#use-request-shaped-feedback-functions). For the override rule when a `RetryableFailure` supplies its own `apply_feedback`, see [Retry-path resolution order](./api_reference.md#retry-path-resolution-order).

Return a fresh request value from `apply_feedback(...)`. Do not mutate the
existing request in place.

## Use `Request(...)` when invoke needs exact args and kwargs

If your invoke function expects more than one positional argument or uses named
keyword arguments, wrap the call shape in `Request(...)`.

```python
from agent_feedback import Request, arun


result = await arun(
    request=Request(
        input="Say hello.",
        model="gpt-5.5",
    ),
    invoke=client.responses.create,
    extract=lambda response: response.output_text,
)
```

That makes the harness call:

```python
await client.responses.create(input="Say hello.", model="gpt-5.5")
```

If your invoke function already takes a single argument, you do not need
`Request(...)`. If you do use it, that same envelope becomes `previous_request`
inside `apply_feedback(...)`. See [request families](./api_reference.md#request-families).

## Use `Runner` when many call sites share the same defaults

`Runner` is a convenience wrapper around the same loop. It is useful when the
same invoke function, extractor, validators, or feedback strategy appear across
multiple call sites.

```python
from agent_feedback import RetryableFailure, Runner


def require_short_answer(text: str) -> None:
    if len(text) > 80:
        raise RetryableFailure(
            "The answer was too long.",
            feedback="Answer in one short sentence.",
        )


runner = Runner(
    invoke=model.ainvoke,
    extract=lambda response: response.output_text,
    validators=[require_short_answer],
    apply_feedback=lambda feedback, previous_request: f"{previous_request}\n\n{feedback}",
    max_attempts=3,
)

result = await runner.arun(request="Greet me briefly.")
```

Start with `arun(...)` first. Reach for `Runner` once you notice repeated loop
configuration. For reusable multi-call-site setups, see [Reuse one pipeline with `Runner`](./patterns.md#reuse-one-pipeline-with-runner).

## What else exists?

- `arun(...)` returns the extracted output directly. See [Entry points](./api_reference.md#entry-points).
- `arun_full(...)` returns a `RunResult` with `output`, `raw_output`,
    `last_request`, `history`, `final_failure`, and `exhausted`. See [History and result models](./api_reference.md#history-and-result-models).
- `TerminalFailure` stops the loop immediately instead of retrying. See [Failure types](./api_reference.md#failure-types).
- `on_exhausted_retries="return_last"` makes `arun(...)` return the final
    extracted output instead of raising the last `RetryableFailure`. See [Entry points](./api_reference.md#entry-points).

## Next reads

- [API Reference](./api_reference.md) for exact signatures and edge-case
  semantics.
- [Patterns](./patterns.md) for `Runner`, decorator recipes, and request-shape
  patterns.