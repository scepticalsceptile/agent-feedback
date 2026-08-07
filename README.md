# agent-feedback

> **Tell your agent what it did wrong in less than 10 lines.**
> A zero-dependency, framework-agnostic Python harness for LLM application validation and stateful feedback retries.

[![PyPI version](https://img.shields.io/pypi/v/agent-feedback.svg)](https://pypi.org/project/agent-feedback/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-feedback.svg)](https://pypi.org/project/agent-feedback/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```python
from agent_feedback import RetryableFailure, arun

def require_tool_call(response):
    if not response.tool_calls:
        raise RetryableFailure(
            "Model did not call a tool.",
            feedback="You must call a tool for this task.",
        )

result = await arun(
    request=messages,
    invoke=llm_invoke,
    validators=[require_tool_call],
    apply_feedback=lambda feedback, request: request + [
        {"role": "system", "content": feedback}
    ],
    max_attempts=3,
)
```

That's the whole idea: **invoke, inspect, give feedback, retry.**

`agent-feedback` is a small, framework-agnostic feedback loop around **any** LLM invocation callable - that `llm_invoke` is YOUR invokable.

It doesn't:

- Replace your model SDK or agent framework
- Assume requests are message lists
- Assume responses are strings
- Force feedback to be appended to a prompt

You define those shapes; the harness just runs the loop.

## Why?

Because LLM output can be **valid and still be wrong**.

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
  validators
    |
    +-------> return None / raise TerminalFailure ---------> done
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

The core loop stages map directly to the leading `arun()` parameters, read top-to-bottom:

1. `request` — The argument or arguments passed to your invocation callable.

2. `invoke` — The callable performing the actual execution/LLM call.

3. `extract` (optional) — Post-processes the raw response into the target shape for validation.

4. `validators` — A list of functions that evaluate the extracted output.

5. `apply_feedback` — Dictates how the feedback transforms the original request for the next attempt.

6. `max_attempts` — The circuit breaker capping total retry attempts.

The output of one function flows naturally as the input to the next. After that,
`max_attempts` and `on_exhausted_retries` define the loop boundary behavior.

For a full guide to the API, see [Getting Started](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/README.md).

## Why not just use Instructor or PydanticAI?

Those libraries already solve an important problem: **does the model's output conform to my schema?**

`agent-feedback` is concerned with a different layer:

**is this output actually acceptable for my application?**

Instructor and PydanticAI already support retrying when their validation mechanisms fail. The difference is where the retry loop lives: theirs is part of their respective framework abstractions; `agent-feedback` wraps an invocation callable you already have.

So you can use it without them, or alongside them:

```python
import instructor

client = instructor.from_provider("openai/gpt-4o-mini")

result = await arun(
    request=Request(
        response_model=UserModel,
        messages=[{"role": "user", "content": "John is 250 years old"}],
    ),
    invoke=client.chat.completions.create,
    validators=[clarify_user_has_reasonable_age],
    apply_feedback=...,
)
```

No framework migration required.

### Why not just a while loop?

```python
for attempt in range(3):
    response = await llm_invoke(request)

    try:
        validate(response)
        return response
    except RetryableFailure as e:
        request = apply_feedback(e.feedback, request)

```

You can. That's essentially what agent-feedback does.

The value isn't hiding a complicated algorithm. It's giving a reusable abstraction to a pattern that tends to grow once you need extraction, multiple validators, structured failures, attempt history, exhaustion handling, and consistent behavior across your application.

If your loop is five lines, write the five-line loop.

If you're writing the same loop repeatedly, use agent-feedback.

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

- Async-first.
- No streaming support.
- No batch orchestration.
- No provider-specific adapters in core.
- No automatic inference about how requests should change.
- No broad retrying of network, authentication, or programming errors.
- No default retry of an unchanged request.

The package is a loop around your callable, not another agent framework.

## Install

```bash
pip install agent-feedback
```

Zero runtime dependencies — stdlib only.

## Further reading

- **Advanced API** — `Runner`, `Request`, callback shapes, controlled failures, and result/history details.
- **Patterns** — request-specific feedback helpers, middleware, decorators, and observability patterns.

## License

MIT
