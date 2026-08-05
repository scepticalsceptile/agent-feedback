"""Tests for the reusable Runner convenience object."""

from __future__ import annotations

import pytest

from agent_feedback import Request, RetryableFailure, Runner, TerminalFailure
from agent_feedback.exceptions import MissingApplyFeedbackError
from tests.fakes import EchoInvokable, FakeRawResponse, SequenceInvokable


@pytest.mark.asyncio
async def test_runner_arun_uses_constructor_defaults_when_overrides_are_omitted(
) -> None:
    runner = Runner(
        invoke=EchoInvokable(lambda request: FakeRawResponse(text=f"echo:{request}")),
        extract=lambda response: response.text,
    )

    result = await runner.arun(request="hello")

    assert result == "echo:hello"


@pytest.mark.asyncio
async def test_runner_arun_full_uses_runner_level_max_attempts_and_structured_path(
) -> None:
    invokable = SequenceInvokable([FakeRawResponse(text="first")])

    def validator(_output: str) -> None:
        raise RetryableFailure("still invalid", feedback="retry")

    runner = Runner(
        invoke=invokable,
        extract=lambda response: response.text,
        validators=[validator],
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        max_attempts=1,
    )

    result = await runner.arun_full(request="initial-request")

    assert result.output == "first"
    assert result.last_request == "initial-request"
    assert result.exhausted is True
    assert isinstance(result.final_failure, RetryableFailure)
    assert len(result.history) == 1


@pytest.mark.asyncio
async def test_runner_local_extract_overrides_runner_default() -> None:
    runner = Runner(
        invoke=EchoInvokable(lambda request: FakeRawResponse(text=f"echo:{request}")),
        extract=lambda response: "global-extract",
    )

    result = await runner.arun(
        request="hello",
        extract=lambda response: response.text,
    )

    assert result == "echo:hello"


@pytest.mark.asyncio
async def test_runner_validators_empty_tuple_disables_runner_validators() -> None:
    def runner_validator(_output: str) -> None:
        raise TerminalFailure("runner validator should be disabled")

    runner = Runner(
        invoke=EchoInvokable(lambda request: FakeRawResponse(text=f"echo:{request}")),
        extract=lambda response: response.text,
        validators=[runner_validator],
    )

    result = await runner.arun(request="hello", validators=())

    assert result == "echo:hello"


@pytest.mark.asyncio
async def test_runner_local_apply_feedback_overrides_runner_default() -> None:
    invokable = SequenceInvokable(
        [
            RetryableFailure("retry", feedback="patch"),
            FakeRawResponse(text="done"),
        ]
    )
    runner = Runner(
        invoke=invokable,
        extract=lambda response: response.text,
        apply_feedback=lambda feedback, request: f"runner::{request}::{feedback}",
        max_attempts=2,
    )

    result = await runner.arun(
        request="initial-request",
        apply_feedback=lambda feedback, request: f"local::{request}::{feedback}",
    )

    assert result == "done"
    assert [call.args for call in invokable.calls] == [
        ("initial-request",),
        ("local::initial-request::patch",),
    ]


@pytest.mark.asyncio
async def test_runner_apply_feedback_none_disables_runner_default() -> None:
    runner = Runner(
        invoke=SequenceInvokable([RetryableFailure("retry", feedback="patch")]),
        apply_feedback=lambda feedback, request: f"runner::{request}::{feedback}",
        max_attempts=2,
    )

    with pytest.raises(MissingApplyFeedbackError, match="apply_feedback"):
        await runner.arun(request="initial-request", apply_feedback=None)


@pytest.mark.asyncio
async def test_runner_uses_runner_level_on_exhausted_retries_for_arun() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="first"),
            FakeRawResponse(text="second"),
        ]
    )

    def validator(_output: str) -> None:
        raise RetryableFailure("still invalid", feedback="retry")

    runner = Runner(
        invoke=invokable,
        extract=lambda response: response.text,
        validators=[validator],
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        on_exhausted_retries="return_last",
        max_attempts=2,
    )

    result = await runner.arun(request="initial-request")

    assert result == "second"


@pytest.mark.asyncio
async def test_runner_local_on_exhausted_retries_overrides_runner_default() -> None:
    invokable = SequenceInvokable(
        [
            FakeRawResponse(text="first"),
            FakeRawResponse(text="second"),
        ]
    )

    def validator(_output: str) -> None:
        raise RetryableFailure("still invalid", feedback="retry")

    runner = Runner(
        invoke=invokable,
        extract=lambda response: response.text,
        validators=[validator],
        apply_feedback=lambda feedback, request: f"{request}|{feedback}",
        on_exhausted_retries="return_last",
        max_attempts=2,
    )

    with pytest.raises(RetryableFailure, match="still invalid"):
        await runner.arun(
            request="initial-request",
            on_exhausted_retries="raise",
        )


@pytest.mark.asyncio
async def test_runner_supports_explicit_request_envelope_defaults() -> None:
    runner = Runner(
        invoke=EchoInvokable(
            lambda *args, **kwargs: {
                "args": args,
                "kwargs": kwargs,
            }
        ),
    )

    result = await runner.arun_full(request=Request("hello", model="gpt-5.5"))

    assert result.output == {
        "args": ("hello",),
        "kwargs": {"model": "gpt-5.5"},
    }
    assert result.last_request == Request("hello", model="gpt-5.5")