# agent-feedback

> **Tell your agent what it did wrong in less than 10 lines.**
> A zero-dependency, framework-agnostic Python harness for LLM application validation and stateful feedback retries.

[![PyPI version](https://img.shields.io/pypi/v/agent-feedback.svg)](https://pypi.org/project/agent-feedback/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-feedback.svg)](https://pypi.org/project/agent-feedback/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```bash
pip install agent-feedback
```

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
    apply_feedback=lambda feedback, previous_request: previous_request + [
        {"role": "system", "content": feedback}
    ],
    max_attempts=3,
)
```

That's the whole idea: **invoke, inspect, give feedback, retry.**

`agent-feedback` is a small, framework-agnostic feedback loop around **any** LLM invocation callable - that `llm_invoke` is YOUR invokable.

It doesn't replace your model SDK or agent framework. It doesn't know or care about invocation shapes. You define those shapes; the harness just runs the loop.

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
    +-------> return None ---------> done
    |
    v
  raise RetryableFailure
    |
    v
  apply_feedback
    |
    v
  request -------------> (back to top)

```

To remember the pipeline, note the stages **map directly to the `arun()` parameters, read top-to-bottom**:

1. `request` — The argument or arguments passed to your invocation callable.
2. `invoke` — The callable performing the actual execution/LLM call.
3. `extract` (optional) — Post-processes the raw response into the target shape for validation.
4. `validators` — A list of functions that evaluate the extracted output.
5. `apply_feedback` — Dictates how the feedback transforms the original request for the next attempt.

The output of one function flows naturally as the input to the next.

For a step-by-step guide, see [Getting Started](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/getting_started.md).

## Built to be spammable, no matter your existing SDK

There's no adapter layer, so there's **almost no integration cost to wrapping every invoke() callsite in your app**, not just the risky ones.

Your extractor and validators naturally adapt to whatever shape each SDK hands back — Anthropic's `.content` blocks, LangChain's `.tool_calls`, whatever. The core loop stays the same even when the SDK does not:

```python
from agent_feedback import arun, Request

# Anthropic — Messages API
await arun(
    request=Request(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=messages,
    ),
    invoke=client.messages.create,
    validators=[require_tool_call],
)

# OpenAI — Responses API
await arun(
    request=Request(
        model="gpt-5.5",
        input=messages,
    ),
    invoke=client.responses.create,
    validators=[require_tool_call],
)

# LangChain — any BaseChatModel
await arun(
    request=messages,
    invoke=model.ainvoke,
    validators=[require_tool_call],
)

# Combine with Instructor
instructor_client = instructor.from_provider("openai/gpt-4o-mini")
await arun(
    request=Request( 
        response_model=UserBaseModel,
        messages=[{"role": "user", "content": "John is 250 years old"}],
    ), 
    invoke=instructor_client.chat.completions.create,
    validators=[user_age_reasonable], # your own validator
)
```

> *Request bundles `args` and `kwargs` for your invoke callable. It's unnecessary when your invoke takes a single argument. In `apply_feedback`, access them via `previous_request.args` and `previous_request.kwargs`.*

This cheapness compounds:

- **Reuse one pipeline everywhere.** Build it once with [Runner](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/patterns.md#reuse-one-pipeline-with-runner), then call it from every site that shares the same `invoke` / `extract` / `apply_feedback`.
- **Raise `RetryableFailure` from anywhere.** Not just validators — raise it inside `invoke` if a provider call produces a recoverable failure, or inside `extract` if parsing fails. The same loop handles it.
- **Use validators as deterministic evals.** A `validator` essentially checks the correctness of an LLM output - which is a free eval. Attach one that records the output and returns `None`, and you can collect pass/fail or quality telemetry at every call site without changing your invocation code.

## Why not just a while loop?

```python
for attempt in range(3):
    response = await llm_invoke(request)

    try:
        validate(response)
        return response
    except RetryableFailure as e:
        request = apply_feedback(e.feedback, request)
```

You can. That's essentially the core of `agent-feedback`.

The value isn't in hiding a complicated algorithm. It's in providing a reusable abstraction around a pattern that tends to grow as your application needs more: extraction, multiple validators, structured failures, attempt history, exhaustion handling, and consistent retry behavior.

**If a five-line loop is all you need, write the five-line loop.**

**If you're writing the same loop repeatedly, use `agent-feedback`.**

## Scope

v1 is deliberately small:

- Async-first.
- No streaming support.
- No batch orchestration.
- No provider-specific adapters in core.
- No automatic inference about how requests should change.

The package is a loop around your callable, not another agent framework. If you need any of these features, you can either build your own abstractions or raise an issue. The API is designed to be extensible.

Today, `agent-feedback` is stdlib-only. Zero-dependency. We will attempt to keep it that way for the foreseeable future.

## Further reading

- [Getting Started](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/getting_started.md) — first successful `arun(...)` loop, extraction, validation, and feedback.
- [API Reference](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/api_reference.md) — exact signatures, callback shapes, failure semantics, and history/result details.
- [Patterns](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/patterns.md) — `Runner` reuse, provider-shaped feedback, decorator recipes, and observability patterns.

## License

MIT
