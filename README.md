# Agent Feedback

> **Tell your agent what it did wrong and have it fix itself.**

[![PyPI version](https://img.shields.io/pypi/v/agent-feedback.svg)](https://pypi.org/project/agent-feedback/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-feedback.svg)](https://pypi.org/project/agent-feedback/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`agent-feedback` is a zero-dependency, framework-agnostic Python harness for validating output → prompting feedback → retrying loops around LLM invocations.

## Quickstart

```bash
pip install agent-feedback
```

```python
from agent_feedback import RetryableFailure, arun
from your_module import violates_permissions

def validate_action_permissions(latest_output):
    if violates_permissions(latest_output):
        raise RetryableFailure(
            "Agent action violated permissions",
            feedback=(
                "Your attempted action violates your current permissions. "
                "Ask the user to grant the necessary permission. "
                "If the action is simple, ask the user to perform it instead."
            ),
        )

response = await arun(
    request=messages, # your own messages
    invoke=llm_invoke, # your own invocation function
    validators=[validate_action_permissions],
    apply_feedback=lambda feedback, previous_request: previous_request + [
        {"role": "system", "content": feedback} # or whatever your message shape looks like
    ],
    max_attempts=3,
)
```

Notice arun doesn't care about invocation input, output, or message shapes - that `llm_invoke` is **your own** invokable. The harness just runs the loop.

## When to use it

**When you need to check validity of LLM output across multiple instances in your codebase.**

Modern agent harnesses may produce:

- A command that is destructive or violates permissions.
- Tool calls that are semantically incorrect - such as trying to cancel a task that has already been completed, or polling a subagent that has finished.
- Tool calls that are structurally incorrect - such as when a required field is missing.
- The same failing command runs multiple times with no change in approach.
- An agent that stops working on a task even though it has a todo list with items still `pending`.

Modern LLMs may not make these mistakes 99% of the time. But in production, over thousands of agentic steps, that 1% can compound quickly.

A local `while` loop is often enough for one check - you won't need this library. The pain appears when you need to write multiple validation loops across the codebase. With `agent-feedback`, you can just add a validator, not another retry loop.

## How it works

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
    +-------> all return None -----> return output
    |
    v
  raise RetryableFailure
    |
    +-------> attempts remain -----> apply_feedback -----> next request
    |
    +-------> no attempts remain --> stop
```

You define these functions. The output of one function in the pipeline flows naturally as the input to the next. The signatures for these pipeline functions can be found in [Request Families](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/api_reference.md#request-families) in the [API reference](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/api_reference.md).

For a step-by-step guide, see [Getting Started](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/getting_started.md).

## Works with your stack

The harness does not import or instantiate provider SDKs. Pass any invocation
callable you already use: OpenAI, Anthropic, LangChain, LlamaIndex, Instructor,
or your own code.

```python
from agent_feedback import Request, arun

# Anthropic Messages API (AsyncAnthropic)
await arun(
    request=Request(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=messages,
    ),
    invoke=anthropic_client.messages.create,
    extract=extract_anthropic_output,
    validators=[validate_output],
    apply_feedback=add_anthropic_feedback,
)

# OpenAI Responses API (AsyncOpenAI)
await arun(
    request=Request(
        model="gpt-5.5",
        input=messages,
    ),
    invoke=openai_client.responses.create,
    extract=extract_openai_output,
    validators=[validate_output],
    apply_feedback=add_openai_feedback,
)

# LangChain chat model
await arun(
    request=messages,
    invoke=model.ainvoke,
    extract=extract_langchain_output,
    validators=[validate_output],
    apply_feedback=add_feedback,
)

# Instructor (async client)
await arun(
    request=Request(
        response_model=StructuredOutput,
        messages=messages,
    ),
    invoke=instructor_client.chat.completions.create,
    validators=[validate_output],
    apply_feedback=add_instructor_feedback,
)
```

Pass a request directly when the callable accepts one positional argument, as
in the LangChain example.

`Request` bundles the exact positional and keyword arguments expected by SDK methods. The `extract_*` and `add_*_feedback` functions above are application-owned adapters to be defined by you.

## Scope

Version 0.1 is deliberately small:

- Async-first.
- No streaming support.
- No batch orchestration.
- No provider-specific adapters in core.
- No automatic inference about how requests should change.

Core is standard-library-only and intended to remain provider-independent. The
package wraps your callable; it is not another agent framework.

## Further reading

- [Getting Started](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/getting_started.md) - first successful `arun(...)` loop, extraction, validation, and feedback.
- [API Reference](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/api_reference.md) - exact signatures, callback shapes, failure semantics, and result details.
- [Patterns](https://github.com/scepticalsceptile/agent-feedback/blob/main/docs/Guides/patterns.md) - `Runner` reuse, provider-shaped feedback, decorators, and observability.

## License

MIT
