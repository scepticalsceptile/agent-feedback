"""Tests for the explicit request envelope."""

from __future__ import annotations

from agent_feedback import Request


def test_request_stores_tuple_args_and_copies_kwargs() -> None:
    kwargs = {"model": "gpt-5.5", "temperature": 0}

    request = Request("hello", **kwargs)
    kwargs["model"] = "changed"

    assert request.args == ("hello",)
    assert request.kwargs == {"model": "gpt-5.5", "temperature": 0}
    assert request.kwargs is not kwargs


def test_request_equality_is_value_based() -> None:
    assert Request("hello", model="gpt-5.5") == Request("hello", model="gpt-5.5")
