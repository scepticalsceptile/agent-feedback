# agent-feedback

> **Tell your agent what it did wrong in less than 10 lines.**
> A zero-dependency, framework-agnostic Python harness for LLM output validation and stateful feedback retries.

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

`agent-feedback` is a small, framework-agnostic feedback loop around _any_ LLM invocation callable - that `llm_invoke` is **YOUR** invokable.

It doesn't replace your model SDK or agent framework. It doesn't know or care about invocation output shapes. You define those shapes; the harness just runs the loop.

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

## 99.99% isn't good enough

Your agent probably isn't stupid. On a frontier model, a well-scoped tool call probably comes back correct 99.99% of the time.

That sounds fine until you multiply it out. At thousands of users running hundreds of thousands of agent steps a day, a 0.01% failure rate isn't an edge case anymore — it's a support queue. You can't fix this by prompting harder - you need **feedback**.

## Framework agnostic - plug and play _today_, no matter your SDK

`agent-feedback` doesn't replace your model SDK or agent framework, and it doesn't know or care about invocation output shapes — Anthropic's `.content` blocks, LangChain's `.tool_calls`, whatever.

This means if you work with _any_ invocation callables in your app, **you can immediately wrap them with `arun()` today at almost no integration cost:**

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

> _Request bundles `args` and `kwargs` for your invoke callable. It's unnecessary when your invoke takes a single argument. In `apply_feedback`, access them via `previous_request.args` and `previous_request.kwargs`._

## The mental model

The pipeline stages map directly to the `arun()` parameters, read top-to-bottom:

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

The output of one function flows naturally as the input to the next. That's it.

Three things worth knowing up front:

- If writing arun() everywhere in your codebase is tedious, build the pipeline once with a reusable object [Runner](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/patterns.md#reuse-one-pipeline-with-runner), then call it from every site that shares the same `invoke` / `extract` / `apply_feedback`.
- You may [raise `RetryableFailure` from anywhere](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/patterns.md#raise-retryablefailure-from-anywhere-in-the-loop), not just validators, to short-curcuit the loop at any stage.
- A `validator` essentially checks the correctness of an LLM output - which is a free deterministic eval! You can integrate an external callback by [using validators as eval hooks.](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/patterns.md#use-validators-as-deterministic-eval-hooks)

For a step-by-step guide, see [Getting Started](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/getting_started.md).

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

This is especially pertinent for output validation. If your codebase has 10s of LLM output validators, you probably want a consistent way to handle them all, rather than a different loop for each one. Attempt history and request access within the pipeline stages are especially tedious to implement consistently across multiple loops.

**If a five-line loop is all you need, write the five-line loop.**

**If you're checking LLM output repeatedly, use `agent-feedback`.**

## Scope

v0.1 is deliberately small:

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
