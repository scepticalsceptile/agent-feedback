"""Tests for the loop entry points and outcome behavior."""

from __future__ import annotations

import pytest

from agent_feedback import (
    Request,
    RetryableFailure,
    TerminalFailure,
    arun,
    arun_full,
)
from agent_feedback.exceptions import MissingApplyFeedbackError
from tests.fakes import (
    EchoInvokable,
    FailingInvokable,
    FakeRawResponse,
    SequenceInvokable,
)


@pytest.mark.asyncio
async def test_arun_full_succeeds_first_try_and_records_successful_attempt() -> None:
    invokable = EchoInvokable(lambda request: FakeRawResponse(text=f"echo:{request}"))

    result = await arun_full(
        invoke=invokable,
        request="hello",
        extract=lambda response: response.text,
    )

    assert result.output == "echo:hello"
    assert result.raw_output == FakeRawResponse(text="echo:hello")
    assert result.last_request == "hello"
    assert result.final_failure is None
    assert result.exhausted is False
    assert len(result.history) == 1
    assert result.history[0].request == "hello"
    assert result.history[0].raw_output == FakeRawResponse(text="echo:hello")
    assert result.history[0].output == "echo:hello"
    assert result.history[0].failure is None
    assert result.history[0].attempt_number == 1


@pytest.mark.asyncio
async def test_arun_full_uses_default_extract_and_expands_request_envelope() -> None:
    invokable = EchoInvokable(
        lambda *args, **kwargs: {
            "args": args,
            "kwargs": kwargs,
        }
    )

    result = await arun_full(
        invoke=invokable,
        request=Request("hello", model="gpt-5.5"),
    )

    assert result.output == {
        "args": ("hello",),
        "kwargs": {"model": "gpt-5.5"},
    }
    assert result.raw_output == {
        "args": ("hello",),
        "kwargs": {"model": "gpt-5.5"},
    }
    assert result.last_request == Request("hello", model="gpt-5.5")
    assert invokable.calls[0].args == ("hello",)
    assert invokable.calls[0].kwargs == {"model": "gpt-5.5"}


@pytest.mark.asyncio
async def test_arun_full_retries_after_invoke_retryable_failure_using_failure_override(
) -> None:
    failure = RetryableFailure(
        "retry invoke",
        feedback="repair request",
        apply_feedback=lambda feedback, request: f"override::{request}::{feedback}",
    )
    invokable = SequenceInvokable([failure, FakeRawResponse(text="done")])

    def run_level_apply_feedback(_feedback: str, _request: str) -> str:
        raise AssertionError("run-level apply_feedback should not be used")

    result = await arun_full(
        invoke=invokable,
        request="initial-request",
        extract=lambda response: response.text,
        apply_feedback=run_level_apply_feedback,
        max_attempts=2,
    )

    assert result.output == "done"
    assert result.last_request == "override::initial-request::repair request"
    assert len(result.history) == 2
    assert result.history[0].raw_output is None
    assert result.history[0].output is None
    assert result.history[0].failure is failure
    assert result.history[1].output == "done"
    assert [call.args for call in invokable.calls] == [
        ("initial-request",),
        ("override::initial-request::repair request",),
    ]


@pytest.mark.asyncio
async def test_arun_full_retries_after_extract_retryable_failure() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="bad"),
            FakeRawResponse(text="good"),
        ]
    )

    def extract(response: FakeRawResponse, request: str) -> str:
        if response.text == "bad":
            raise RetryableFailure("retry extract", feedback="patch")
        return f"{request}|{response.text}"

    result = await arun_full(
        invoke=invokable,
        request="initial-request",
        extract=extract,
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        max_attempts=2,
    )

    assert result.output == "initial-request|patch|good"
    assert result.last_request == "initial-request|patch"
    assert len(result.history) == 2
    assert result.history[0].raw_output == FakeRawResponse(text="bad")
    assert result.history[0].output is None
    assert isinstance(result.history[0].failure, RetryableFailure)
    assert result.history[1].output == "initial-request|patch|good"
    assert [call.args for call in invokable.calls] == [
        ("initial-request",),
        ("initial-request|patch",),
    ]


@pytest.mark.asyncio
async def test_arun_full_exhausts_retries_and_returns_final_failure() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="first"),
            FakeRawResponse(text="second"),
        ]
    )

    def validator(_output: str) -> None:
        raise RetryableFailure("still invalid", feedback="retry")

    result = await arun_full(
        invoke=invokable,
        request="initial-request",
        extract=lambda response: response.text,
        validators=[validator],
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        max_attempts=2,
    )

    assert result.output == "second"
    assert result.raw_output == FakeRawResponse(text="second")
    assert result.last_request == "initial-request|retry"
    assert result.exhausted is True
    assert isinstance(result.final_failure, RetryableFailure)
    assert str(result.final_failure) == "still invalid"
    assert len(result.history) == 2
    assert [attempt.attempt_number for attempt in result.history] == [1, 2]
    assert result.history[0].output == "first"
    assert result.history[1].output == "second"


@pytest.mark.asyncio
async def test_arun_full_returns_terminal_failure_result_without_retrying() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="bad"),
            FakeRawResponse(text="unused"),
        ]
    )

    def validator(_output: str) -> None:
        raise TerminalFailure("stop now")

    result = await arun_full(
        invoke=invokable,
        request="initial-request",
        extract=lambda response: response.text,
        validators=[validator],
        max_attempts=3,
    )

    assert result.output == "bad"
    assert result.raw_output == FakeRawResponse(text="bad")
    assert result.last_request == "initial-request"
    assert result.exhausted is False
    assert isinstance(result.final_failure, TerminalFailure)
    assert str(result.final_failure) == "stop now"
    assert len(result.history) == 1
    assert invokable.call_count == 1


@pytest.mark.asyncio
async def test_arun_full_propagates_unexpected_invoke_exception_unchanged() -> None:
    invokable = FailingInvokable(RuntimeError("transport broke"))

    with pytest.raises(RuntimeError, match="transport broke"):
        await arun_full(
            invoke=invokable,
            request="initial-request",
            extract=lambda response: response,
        )


@pytest.mark.asyncio
async def test_arun_full_rejects_max_attempts_less_than_one() -> None:
    invokable = EchoInvokable(lambda request: FakeRawResponse(text=f"echo:{request}"))

    with pytest.raises(ValueError, match="max_attempts"):
        await arun_full(
            invoke=invokable,
            request="hello",
            extract=lambda response: response.text,
            max_attempts=0,
        )


@pytest.mark.asyncio
async def test_arun_full_raises_missing_apply_feedback_error_without_retry_path(
) -> None:
    invokable = SequenceInvokable([FakeRawResponse(text="bad")])

    def validator(_output: str) -> None:
        raise RetryableFailure("needs retry", feedback="repair")

    with pytest.raises(MissingApplyFeedbackError, match="apply_feedback"):
        await arun_full(
            invoke=invokable,
            request="initial-request",
            extract=lambda response: response.text,
            validators=[validator],
            max_attempts=2,
        )


@pytest.mark.asyncio
async def test_arun_returns_output_on_success() -> None:
    invokable = EchoInvokable(lambda request: FakeRawResponse(text=f"echo:{request}"))

    result = await arun(
        invoke=invokable,
        request="hello",
        extract=lambda response: response.text,
    )

    assert result == "echo:hello"


@pytest.mark.asyncio
async def test_arun_raises_terminal_failure() -> None:
    invokable = SequenceInvokable([FakeRawResponse(text="bad")])

    def validator(_output: str) -> None:
        raise TerminalFailure("stop now")

    with pytest.raises(TerminalFailure, match="stop now"):
        await arun(
            invoke=invokable,
            request="initial-request",
            extract=lambda response: response.text,
            validators=[validator],
        )


@pytest.mark.asyncio
async def test_arun_raises_final_retryable_failure_on_exhaustion_by_default() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="first"),
            FakeRawResponse(text="second"),
        ]
    )

    def validator(_output: str) -> None:
        raise RetryableFailure("still invalid", feedback="retry")

    with pytest.raises(RetryableFailure, match="still invalid"):
        await arun(
            invoke=invokable,
            request="initial-request",
            extract=lambda response: response.text,
            validators=[validator],
            apply_feedback=lambda feedback, request: f"{request}|{feedback}",
            max_attempts=2,
        )


@pytest.mark.asyncio
async def test_arun_returns_last_output_on_exhaustion_with_return_last() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="first"),
            FakeRawResponse(text="second"),
        ]
    )

    def validator(_output: str) -> None:
        raise RetryableFailure("still invalid", feedback="retry")

    result = await arun(
        invoke=invokable,
        request="initial-request",
        extract=lambda response: response.text,
        validators=[validator],
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        on_exhausted_retries="return_last",
        max_attempts=2,
    )

    assert result == "second"


@pytest.mark.asyncio
async def test_arun_returns_none_when_return_last_has_no_final_output() -> None:
    invokable = SequenceInvokable(
        [
            RetryableFailure("retry one", feedback="repair-1"),
            RetryableFailure("retry two", feedback="repair-2"),
        ]
    )

    result = await arun(
        invoke=invokable,
        request="initial-request",
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        on_exhausted_retries="return_last",
        max_attempts=2,
    )

    assert result is None