# agent-feedback

## Tell your agent what it did wrong, and let it try again

```python
from agent_feedback import RetryableFailure, arun

def require_tool_call(response):
    if not response.tool_calls:
        raise RetryableFailure(
            "Model did not call a tool.",
            feedback="You must call a tool for this task.",
        )

result = await arun(
    invoke=model.invoke,
    request=messages,
    validators=[require_tool_call],
    apply_feedback=lambda feedback, request: request + [
        {"role": "system", "content": feedback}
    ],
    max_attempts=3,
)
```

That's the whole idea: **invoke, inspect, give feedback, retry.**

`agent-feedback` is a small, framework-agnostic feedback loop around **any** LLM invocation callable.

It doesn't replace your model SDK or agent framework, and it doesn't assume that requests are messages, responses are strings, or validation is schema-based.

## Why?

LLM output can be **valid and still be wrong**.

A schema can tell you that this is a valid tool call:

```python
{
    "origin": "NYC",
    "destination": "NYC",
}
```

It can't tell you that the user probably didn't mean to search for a flight from a city to itself.

That's application-level validation:

```python
def validate_flight_search(tool_call):
    if tool_call.name != "search_flights":
        raise RetryableFailure(
            "Wrong tool selected.",
            feedback="Use the search_flights tool for this request.",
        )

    if tool_call.input["origin"] == tool_call.input["destination"]:
        raise RetryableFailure(
            "Origin and destination are identical.",
            feedback="Choose a destination different from the origin.",
        )
```

The feedback becomes context for the next attempt.

## The mental model

```text

 request
    |
    v
  invoke
    |
    v
  extract (optional)
    |
    v
  validate
    |
    +-------> return None -------------> done
    |
    v
  raise RetryableFailure
    |
    v
  apply_feedback
    |
    v
  request -----------> (back to top)

```

The important part is what the loop **doesn't** assume.

Terminal failures stop immediately instead of looping.

Your request might be a string, a message list, a request object, or something entirely specific to your application. Your response might be a provider object, a parsed model, or a wrapper around either. You define `invoke`, optional `extract`, `validators`, and `apply_feedback`; the harness just runs the loop.

## Why not just use Instructor or PydanticAI?

Those libraries already solve an important problem: **does the model's output conform to my schema?**

`agent-feedback` is concerned with a different layer:

**is this output actually acceptable for my application?**

Instructor and PydanticAI already support retrying when their validation mechanisms fail. The difference is where the retry loop lives: theirs is part of their respective framework abstractions; `agent-feedback` wraps an invocation callable you already have.

So you can use it alongside them, or without them.

```python
result = await arun(
    invoke=agent.run,
    request=prompt,
    validators=[check_business_rules],
    apply_feedback=...,
)
```

No framework migration required.

## Four things

The core API deliberately stays small. It is really just four hooks:

```python
result = await arun(
    invoke=model.ainvoke,  # perform the actual call
    request=messages,
    extract=lambda response: response.output_text,  # optional: pick what you validate
    validators=[check_business_rules],  # accept or reject the extracted output
    apply_feedback=append_retry_feedback,  # build the next request from feedback
)
```

`extract` is optional; omit it if the raw response is already the thing you want to validate.

Validators return `None` on success. A `RetryableFailure` asks for another attempt; a `TerminalFailure` stops immediately.

`apply_feedback` is intentionally **not universal**. `agent-feedback` doesn't assume that every request is an appendable message list.

For a different request shape, write a different function.

```python
apply_feedback=lambda feedback, request: {
    **request,
    "prompt": f"{request['prompt']}\n\n{feedback}",
}
```

The package provides narrow helpers for common request families, but they are conveniences rather than a universal request adapter.

## Controlled failure

There are two kinds of deliberate failure:

```python
RetryableFailure(...)
TerminalFailure(...)
```

A `RetryableFailure` means:

> This attempt isn't acceptable. Here's what the model should know before trying again.

```python
raise RetryableFailure(
    "The selected destination was invalid.",
    feedback="Choose a destination different from the origin.",
)
```

A `TerminalFailure` means:

> Stop. Don't ask the model to try again.

There is no default "retry the same request" behavior. If a failure is retryable, you must define how its feedback changes the next request.

Unexpected exceptions propagate normally.

## Reuse the loop

If the same invocation, extraction, or feedback behavior is used across a codebase, `Runner` lets you package those defaults:

```python
runner = Runner(
    invoke=model.ainvoke,
    extract=lambda response: response,
    apply_feedback=lambda feedback, request: request + [
        {"role": "system", "content": feedback}
    ],
    max_attempts=3,
)

result = await runner.arun(
    request=messages,
    validators=[require_tool_call],
)
```

`Runner` is only a convenience. It delegates to the same execution model as `arun`.

## Inspecting attempts

Most calls only need the final output:

```python
result = await arun(...)
```

When you need diagnostics or the full attempt history:

```python
result = await arun_full(...)

result.output
result.raw_output
result.last_request
result.history
result.final_failure
```

`AttemptHistory` is an audit trail for advanced validation, retry logic, and observability. It isn't a second orchestration framework.

## Scope

v1 is deliberately small:

* Async-first.
* No streaming support.
* No batch orchestration.
* No provider-specific adapters in core.
* No automatic inference about how requests should change.
* No broad retrying of network, authentication, or programming errors.
* No default retry of an unchanged request.

The package is a loop around your callable, not another agent framework.

## Install

```bash
pip install agent-feedback
```

Zero runtime dependencies — stdlib only.

## Further reading

* **Advanced API** — `Runner`, `Request`, callback shapes, controlled failures, and result/history details.
* **Patterns** — request-specific feedback helpers, middleware, decorators, and observability patterns.

## License

MIT
