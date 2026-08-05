"""Tests for internal callback and invoke utilities."""

from __future__ import annotations

import pytest

from agent_feedback import AttemptHistory, Request, RetryableFailure
from agent_feedback._callbacks import call_apply_feedback, call_extract, call_validator
from agent_feedback._invoke import invoke_request
from tests.fakes import EchoInvokable, FakeRawResponse, SemanticRequest


@pytest.mark.asyncio
async def test_call_extract_supports_sync_raw_output_only_shape() -> None:
    raw_output = FakeRawResponse(text="trim me")
    history = AttemptHistory(max_attempts=3)

    def extract(value: FakeRawResponse) -> str:
        return value.text.upper()

    result = await call_extract(extract, raw_output, "request", history)

    assert result == "TRIM ME"


@pytest.mark.asyncio
async def test_call_extract_supports_sync_raw_output_request_shape() -> None:
    request = SemanticRequest(prompt="Summarize", system="Be terse")
    raw_output = FakeRawResponse(text="response")
    history = AttemptHistory(max_attempts=3)

    def extract(
        received_raw_output: FakeRawResponse,
        received_request: SemanticRequest,
    ) -> tuple[str, SemanticRequest]:
        return received_raw_output.text, received_request

    result = await call_extract(extract, raw_output, request, history)

    assert result == ("response", request)


@pytest.mark.asyncio
async def test_call_extract_supports_async_raw_output_request_history_shape() -> None:
    request = Request("hello", model="gpt-5.5")
    raw_output = FakeRawResponse(text="response")
    history = AttemptHistory(max_attempts=3)

    async def extract(
        received_raw_output: FakeRawResponse,
        received_request: Request,
        received_history: AttemptHistory,
    ) -> tuple[Request, str, AttemptHistory]:
        return received_request, received_raw_output.text, received_history

    result = await call_extract(extract, raw_output, request, history)

    assert result == (request, "response", history)


@pytest.mark.asyncio
async def test_call_validator_supports_sync_and_async_shapes() -> None:
    history = AttemptHistory(max_attempts=3)
    seen: list[tuple[str, object]] = []

    def validate_one(output: str) -> None:
        seen.append(("one", output))

    async def validate_two(output: str, received_history: AttemptHistory) -> None:
        seen.append(("two", output))
        assert received_history is history

    await call_validator(validate_one, "first", history)
    await call_validator(validate_two, "second", history)

    assert seen == [("one", "first"), ("two", "second")]


@pytest.mark.asyncio
async def test_call_validator_rejects_non_none_return_values() -> None:
    history = AttemptHistory(max_attempts=3)

    def invalid_validator(_output: str) -> bool:
        return False

    with pytest.raises(TypeError, match="must return None on success"):
        await call_validator(invalid_validator, "output", history)


@pytest.mark.asyncio
async def test_call_apply_feedback_supports_sync_and_async_shapes() -> None:
    request = SemanticRequest(prompt="Initial prompt")
    error = RetryableFailure("retry", feedback="add details")
    history = AttemptHistory(max_attempts=3)

    def apply_two(feedback: str, received_request: SemanticRequest) -> str:
        assert received_request is request
        return f"{received_request.prompt} :: {feedback}"

    async def apply_four(
        feedback: str,
        received_request: SemanticRequest,
        received_error: RetryableFailure,
        received_history: AttemptHistory,
    ) -> Request:
        assert received_request is request
        assert received_error is error
        assert received_history is history
        return Request(received_request.prompt, feedback=feedback)

    assert (
        await call_apply_feedback(
            apply_two,
            "add details",
            request,
            error,
            history,
        )
        == "Initial prompt :: add details"
    )
    assert (
        await call_apply_feedback(
            apply_four,
            "add details",
            request,
            error,
            history,
        )
        == Request("Initial prompt", feedback="add details")
    )


@pytest.mark.asyncio
async def test_callback_helpers_reject_unsupported_signatures() -> None:
    history = AttemptHistory(max_attempts=3)
    error = RetryableFailure("retry", feedback="fix it")

    def invalid_extract(*_args: object) -> None:
        return None

    def invalid_validator(_output: str, *, required: bool) -> None:
        return None

    def invalid_apply_feedback(
        feedback: str,
        request: str,
        error: Exception,
        history: AttemptHistory,
        extra: object,
    ) -> str:
        return request

    with pytest.raises(TypeError, match="extract callback"):
        await call_extract(invalid_extract, "raw", "request", history)

    with pytest.raises(TypeError, match="validator callback"):
        await call_validator(invalid_validator, "output", history)

    with pytest.raises(TypeError, match="apply_feedback callback"):
        await call_apply_feedback(
            invalid_apply_feedback,
            "feedback",
            "request",
            error,
            history,
        )


@pytest.mark.asyncio
async def test_invoke_request_passes_bare_request_as_single_positional_argument(
) -> None:
    invokable = EchoInvokable()
    request = SemanticRequest(prompt="Say hello", system="Be brief")

    result = await invoke_request(invokable, request)

    assert result is request
    assert invokable.call_count == 1
    assert invokable.calls[0].args == (request,)
    assert invokable.calls[0].kwargs == {}


@pytest.mark.asyncio
async def test_invoke_request_expands_request_envelope_and_supports_sync_invoke(
) -> None:
    seen: dict[str, object] = {}

    def invoke(*args: object, **kwargs: object) -> dict[str, object]:
        seen["args"] = args
        seen["kwargs"] = dict(kwargs)
        return {
            "args": args,
            "kwargs": dict(kwargs),
        }

    request = Request("hello", model="gpt-5.5")

    result = await invoke_request(invoke, request)

    assert result == {
        "args": ("hello",),
        "kwargs": {"model": "gpt-5.5"},
    }
    assert seen == {
        "args": ("hello",),
        "kwargs": {"model": "gpt-5.5"},
    }
