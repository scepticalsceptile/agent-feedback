"""Focused tests for the shared fake invokables.

These are intentionally narrow: they lock down the fake behavior that later
loop tests will depend on without assuming anything about the harness API yet.
"""

from __future__ import annotations

import pytest

from tests.fakes import (
    EchoInvokable,
    FailingInvokable,
    FakeRawResponse,
    SemanticRequest,
    SequenceInvokable,
)


@pytest.mark.asyncio
async def test_sequence_invokable_returns_and_raises_from_script() -> None:
    error = ValueError("bad shape")
    invokable = SequenceInvokable([
        FakeRawResponse(text="first"),
        error,
        "third",
    ])

    first = await invokable("request-1")

    with pytest.raises(ValueError, match="bad shape"):
        await invokable("request-2")

    third = await invokable("request-3")

    assert first == FakeRawResponse(text="first")
    assert third == "third"
    assert invokable.call_count == 3
    assert [call.args for call in invokable.calls] == [
        ("request-1",),
        ("request-2",),
        ("request-3",),
    ]


@pytest.mark.asyncio
async def test_echo_invokable_can_echo_bare_requests() -> None:
    invokable = EchoInvokable()
    request = SemanticRequest(prompt="Say hello", system="Be brief")

    result = await invokable(request)

    assert result is request
    assert invokable.call_count == 1
    assert invokable.calls[0].args == (request,)
    assert invokable.calls[0].kwargs == {}


@pytest.mark.asyncio
async def test_echo_invokable_can_transform_explicit_call_shapes() -> None:
    invokable = EchoInvokable(
        lambda *args, **kwargs: {
            "args": args,
            "kwargs": kwargs,
            "summary": f"{kwargs['model']}:{args[0]}",
        }
    )

    result = await invokable("hello", model="gpt-5.5")

    assert result == {
        "args": ("hello",),
        "kwargs": {"model": "gpt-5.5"},
        "summary": "gpt-5.5:hello",
    }
    assert invokable.calls[0].kwargs == {"model": "gpt-5.5"}


@pytest.mark.asyncio
async def test_failing_invokable_raises_known_exception_and_records_call() -> None:
    error = RuntimeError("transport broke")
    invokable = FailingInvokable(error)

    with pytest.raises(RuntimeError, match="transport broke"):
        await invokable("hello", model="gpt-5.5")

    assert invokable.call_count == 1
    assert invokable.calls[0].args == ("hello",)
    assert invokable.calls[0].kwargs == {"model": "gpt-5.5"}


@pytest.mark.asyncio
async def test_sequence_invokable_raises_when_script_is_exhausted() -> None:
    invokable = SequenceInvokable(["only-result"])

    assert await invokable("request") == "only-result"

    with pytest.raises(AssertionError, match="ran out of scripted steps"):
        await invokable("request")