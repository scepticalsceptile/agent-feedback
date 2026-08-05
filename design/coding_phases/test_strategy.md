# Test Strategy Plan

## Goal

Drive the library in a TDD-ish way with fake invokables and fake request/output
types, without hitting any real LLM providers or external services.

The tests should prove the loop semantics first and the packaging niceties
second.

## Testing principles

- no network access
- no real model SDK calls
- prefer tiny fake objects over mocks when possible
- make every test name read like a behavior statement
- write tests against the public API unless a private helper is especially hard
  to reach otherwise

## Core fake building blocks

### Fake request shapes

- bare string request
- bare list request, especially message-like lists
- explicit `Request(*args, **kwargs)` envelope
- a custom semantic request object for one or two tests

### Fake raw outputs

- plain string raw output
- simple dataclass raw output with fields like `text` or `tool_calls`
- raw output objects that force `extract()` to do real work

### Fake invokables

- `SequenceInvokable`: returns or raises from a scripted sequence
- `EchoInvokable`: returns the request or a direct derivative of it
- `FailingInvokable`: raises a known exception immediately
- invoke wrappers that raise `RetryableFailure`
- invoke wrappers that raise `TerminalFailure`

### Shared recording helpers

- call recorder for received requests
- helper to capture attempt counts
- helper to assert a returned request is a fresh object when expected

## Minimum behavior matrix

### Top-level loop outcomes

1. succeeds on the first try
2. succeeds after three attempts
3. exhausts retries and raises by default in `arun(...)`
4. exhausts retries and returns last output with
   `on_exhausted_retries="return_last"`
5. `arun_full(...)` returns `RunResult` with `exhausted=True`
6. `TerminalFailure` stops immediately and raises in `arun(...)`
7. uncaught invoke exception propagates unchanged

### Invoke-stage behavior

1. bare request calls `invoke(request)`
2. explicit `Request(...)` calls `invoke(*args, **kwargs)`
3. invoke may raise `RetryableFailure` and continue the loop
4. invoke may raise `TerminalFailure` and stop the loop

### Extract-stage behavior

1. extractor can be `extract(raw_output)`
2. extractor can be `extract(raw_output, request)`
3. extractor can be `extract(raw_output, request, history)`
4. extractor may be sync or async
5. extractor may raise `RetryableFailure`
6. extractor may raise `TerminalFailure`

### Validator behavior

1. validator can be `validator(output)`
2. validator can be `validator(output, history)`
3. validator may be sync or async
4. validator returning `None` means success
5. validator raising `RetryableFailure` retries
6. validator raising `TerminalFailure` stops
7. validator returning `False` or any non-`None` value raises `TypeError`

### Apply-feedback behavior

1. call-level `apply_feedback` is used when failure has no override
2. `failure.apply_feedback` overrides the call-level one
3. `apply_feedback` can be sync or async
4. bare request remains bare inside `apply_feedback`
5. explicit `Request(...)` remains wrapped inside `apply_feedback`
6. missing apply-feedback path is a configuration error

### History and result behavior

1. `Attempt.raw_output` is the exact invoke result
2. `Attempt.output` is the extracted output
3. `Attempt.failure` is recorded on failed attempts
4. attempt numbers increase monotonically
5. `RunResult.final_failure` is correct on exhaustion or terminal stop
6. `RunResult.last_request` is the request used for the final attempt
7. history order matches actual execution order

### Helper behavior

1. helpers return fresh request values
2. bare-request helpers do not mutate the original request
3. `Request(...)` helpers do not mutate original `args` or `kwargs`
4. helper output is suitable for immediate reinvocation

## Suggested `tests/` file layout

```text
tests/
    conftest.py
    fakes.py
    test_public_api.py
    test_request_model.py
    test_callback_shapes.py
    test_loop_outcomes.py
    test_failures.py
    test_history_and_results.py
    test_helpers.py
```

## TDD writing order

1. request and failure model tests
2. callback-shape tests
3. `arun_full(...)` loop outcome tests
4. `arun(...)` convenience behavior tests
5. helper tests

## Test-plan acceptance criteria

- no test depends on a real SDK or provider
- the behavior matrix above is covered directly
- fake invokables are readable enough to debug failures quickly
- history assertions prove the raw-versus-extracted distinction clearly
