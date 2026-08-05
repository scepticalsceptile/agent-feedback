"""Tests for controlled failure models."""

from __future__ import annotations

from typing import Any

from agent_feedback import RetryableFailure, TerminalFailure


def test_retryable_failure_stores_feedback_and_copies_metadata() -> None:
    metadata = {"field": "answer"}

    def apply_feedback(*_args: Any) -> str:
        return "next-request"

    failure = RetryableFailure(
        "needs retry",
        feedback="Please answer with JSON.",
        apply_feedback=apply_feedback,
        metadata=metadata,
    )
    metadata["field"] = "changed"

    assert str(failure) == "needs retry"
    assert failure.message == "needs retry"
    assert failure.feedback == "Please answer with JSON."
    assert failure.apply_feedback is apply_feedback
    assert failure.metadata == {"field": "answer"}
    assert failure.metadata is not metadata


def test_terminal_failure_preserves_message() -> None:
    failure = TerminalFailure("stop now")

    assert str(failure) == "stop now"
    assert failure.message == "stop now"
