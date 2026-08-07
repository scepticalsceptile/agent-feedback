# agent-feedback

`agent_feedback` is a small Python library for one job:

take a normal LLM call and wrap it in a loop that can:

1. call the model
2. pull out the part you care about
3. check whether it is acceptable
4. try again with feedback if it is not

You keep your own model client and your own request shape. The library only
adds the retry loop.

## A Tiny Example

If your model call already returns exactly what you want, the smallest example
can be this simple:

```python
from agent_feedback import arun


result = await arun(
	request="Say hello in one short sentence.",
	invoke=model.ainvoke,
)
```

If your SDK returns a bigger response object, add a small extractor:

```python
from agent_feedback import arun


result = await arun(
	request="Say hello in one short sentence.",
	invoke=model.ainvoke,
	extract=lambda response: response.output_text,
)
```

If your SDK uses `response.text`, `response.content`, or something else, just
change that lambda.

## The Pipeline

This is the whole mental model:

```text
request
  |
  v
invoke(request)
  |
  v
raw response
  |
  v
extract(response, ...)
  |
  v
output
  |
  +--> valid -> return output
  |
  \--> invalid -> raise RetryableFailure(feedback="...")
                   |
                   v
         apply_feedback(feedback, request, ...)
                   |
                   v
               next request
                   |
                   v
                 retry
```

In plain English:

- `request` is whatever you would normally pass to your model
- `invoke` is your existing async model call
- `response` is the raw thing your SDK returns
- `extract` pulls out the piece you want to validate
- `validator` checks that extracted value
- `RetryableFailure` says "try again, and here is the feedback to add"
- `apply_feedback` builds the next request

## A Simple Retry Example

This is a more realistic first example.

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
	apply_feedback=lambda feedback, request: f"{request}\n\n{feedback}",
	max_attempts=3,
)
```

What happens here:

- `invoke` calls your model
- `extract` pulls out the text
- `must_start_with_hello(...)` checks the text
- if the text is bad, it raises `RetryableFailure`
- `apply_feedback` appends that feedback to the old request
- the harness tries again

## The Two Main Entry Points

### `arun(...)`

Start here.

`arun(...)` returns the extracted output directly.

- if the run succeeds, you get the output
- if a `TerminalFailure` happens, it raises immediately
- if retries run out, it raises the final `RetryableFailure` by default
- if you pass `on_exhausted_retries="return_last"`, it returns the final
  extracted output instead

That returned value may be `None` if the final attempt never produced extracted
output.

### `arun_full(...)`

Use this when you want debugging information.

It returns a `RunResult` with:

- `output`
- `raw_output`
- `last_request`
- `history`
- `final_failure`
- `exhausted`

Example:

```python
from agent_feedback import arun_full


run = await arun_full(
	request="Say hello in one short sentence.",
	invoke=model.ainvoke,
	extract=lambda response: response.output_text,
)

print(run.output)
print(run.history)
```

## Callback Shapes

The library supports a small number of callback shapes on purpose.

Extractor callbacks are response-first:

```python
extract(response)
extract(response, request)
extract(response, request, history)
```

Validator callbacks:

```python
validator(output)
validator(output, history)
```

Apply-feedback callbacks:

```python
apply_feedback(feedback, request)
apply_feedback(feedback, request, error)
apply_feedback(feedback, request, error, history)
```

These can be sync or async.

Validators must return `None` on success. If they want a retry or a stop, they
should raise an exception instead.

## The Two Failure Types

### `RetryableFailure`

Raise this when the answer is not good enough yet, but another attempt might
fix it.

It must include `feedback=...`, because that feedback is what the next request
will be built from.

### `TerminalFailure`

Raise this when the run should stop immediately and not retry.

## Most People Can Ignore `Request(...)` At First

If your model call is shaped like `invoke(request)`, just pass the request
directly.

`Request(...)` is only for cases where your model call needs exact args and
kwargs.

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

## Most People Can Ignore `Runner` Too

There is also a `Runner` object for reusing the same defaults across many runs.

If you are seeing this package for the first time, start with `arun(...)` and
`arun_full(...)` first.

## One Important Rule: Do Not Mutate Requests In Place

When `apply_feedback(...)` builds the next request, return a fresh value.

Good:

```python
apply_feedback=lambda feedback, request: request + [feedback]
```

Bad:

```python
def apply_feedback(feedback, request):
	request.append(feedback)
	return request
```

Why this matters: the harness stores history, and mutating an old request can
make that history misleading.

## Current Limits

- async-first only
- no built-in helper families yet
- no streaming support yet
- no provider-specific adapters in the core package
- unexpected exceptions are not wrapped and usually propagate unchanged

## Development

For local development in this repository:

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
