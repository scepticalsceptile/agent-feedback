# agent-feedback

**Tell your agent what it did wrong, and let it try again — in about 10 lines, with the `invoke` you already have.**

[![PyPI](https://img.shields.io/pypi/v/agent-feedback)](https://pypi.org/project/agent-feedback/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)

```python
from agent_feedback import RetryableFailure, arun, append_feedback_message


def require_tool_call(response):
    if not response.tool_calls:
        raise RetryableFailure(
            "Model answered in prose instead of calling a tool.",
            feedback="You must call a tool for this task — don't respond in plain text.",
        )


result = await arun(
    invoke=model.ainvoke,
    request=messages,
    validators=[require_tool_call],
    apply_feedback=append_feedback_message(role="user"),
    max_attempts=3,
)
```

That's the whole library: call the model, check the result, and if it's not
good enough, tell it why and try again. No new mental model, no subclassing,
no schema DSL — `model.ainvoke` above is *your* existing invoke call,
untouched.

## Install

```bash
pip install agent-feedback
```

Zero runtime dependencies — stdlib only.

## The mental model

```
request
   │
   ▼
invoke(request) ────────► raw response
   │
   ▼
extract(response, ...) ──► output
   │
   ├── valid ────────────► return output
   │
   └── invalid ──────────► raise RetryableFailure(feedback=...)
                               │
                               ▼
                   apply_feedback(feedback, request, ...) ─► next request
                               │
                               ▼
                             retry
```

Most SDKs don't hand you "the answer" directly — OpenAI's Responses API
buries it in `response.output_text`, Anthropic's Messages API buries it in a
list of content blocks. `extract` is where you dig it out. If the raw
response is already the thing you want to check (like `response.tool_calls`
above), skip `extract` entirely — it defaults to returning the response
as-is.

## Why not just use Instructor or PydanticAI?

Those libraries answer a different question: *does the model's output match
my schema?* Both already retry when it doesn't — Instructor re-asks when a
Pydantic field validator raises, PydanticAI re-asks when you raise
`ModelRetry`. If your problem is shape, use them.

`agent_feedback` answers a different question: *is this output actually
acceptable* — which schema validation can't tell you. This tool call is
perfectly valid: correct types, every required field, passes any Pydantic
model you'd write for it. It's still wrong.

```python
def valid_flight_search(tool_call):
    origin = tool_call.input["origin"]
    destination = tool_call.input["destination"]
    if origin == destination:
        raise RetryableFailure(
            "Origin and destination were identical.",
            feedback=(
                f"You searched a flight from {origin} to {destination} — "
                "that's the same city. Pick a real destination."
            ),
        )
```

Nothing about `{"origin": "NYC", "destination": "NYC"}` fails a schema. It
fails *your business logic*, and only you know what that is.

This isn't a replacement for Instructor or PydanticAI — it's a layer that
doesn't care whether you're using them. `invoke=` can just as easily be a
PydanticAI agent's `.run` or an Instructor-wrapped client; `agent_feedback`
only cares that it's a callable.

## Built to be spammable

There's no adapter step, so there's roughly zero cost to wrapping *every*
call site in your app, not just the risky ones. Same loop, any SDK:

```python
# Anthropic — Messages API
await arun(
    invoke=client.messages.create,
    request=Request(model="claude-sonnet-4-6", max_tokens=1024, messages=messages),
    validators=[require_tool_call],
)

# OpenAI — Responses API
await arun(
    invoke=client.responses.create,
    request=Request(model="gpt-5.5", input=messages),
    validators=[require_tool_call],
)

# LangChain — any BaseChatModel
await arun(
    invoke=model.ainvoke,
    request=messages,
    validators=[require_tool_call],
)
```

(Your extractor and validator naturally adapt to whatever shape each SDK
hands back — Anthropic's `.content` blocks, LangChain's `.tool_calls`,
whatever. What doesn't change is the loop around them.)

That cheapness compounds:

- **Reuse one pipeline everywhere.** Build it once with `Runner`, call it
  from every site that shares the same `invoke` / `extract` / `apply_feedback`.
- **Raise `RetryableFailure` from anywhere**, not just validators — inside
  `invoke` itself if a provider call throws, inside `extract` if parsing
  fails. Same loop catches it.
- **Validators are free evals.** Attach one that just logs and returns
  `None` — you get pass/fail telemetry on every call site for nothing.

And because `RetryableFailure` is just an exception, you can go one step
further and make *any* function retryable with a decorator:

```python
def retryable(fn):
    async def wrapped(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            raise RetryableFailure(str(exc), feedback=str(exc)) from exc
    return wrapped


result = await arun(invoke=retryable(some_flaky_function), request=payload)
```

Now anything that throws feeds the model its own error message and tries
again.

## Scope

- Async-first. A sync wrapper may come later — not in v1.
- No streaming support — validating mid-stream is a different design problem.
- No batch orchestration, no provider-specific adapters shipped in core.
- No default "retry the same request" behavior — you always say what changes.
- Unexpected exceptions (network errors, auth failures, bugs) propagate
  as-is. Wrap them yourself if you want them treated as retryable — see the
  decorator above.
- `AttemptHistory` is a read-only audit trail, not a lifecycle framework.

## Further reading

[`ADVANCED.md`](./ADVANCED.md) covers: the two failure types in depth, the
`Runner` object, `Request(...)` internals, typing your callbacks, the full
callback-shape reference, and the built-in helper families.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy src tests
uv run pytest
uv build
uv run twine check dist/*
```

## License

MIT
