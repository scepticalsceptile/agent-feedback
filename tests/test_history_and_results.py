"""Tests for attempt history and structured result models."""

from __future__ import annotations

from agent_feedback import Attempt, AttemptHistory, RunResult, TerminalFailure


def test_empty_attempt_history_has_no_last_attempt() -> None:
    history = AttemptHistory(max_attempts=3)

    assert len(history) == 0
    assert history.last_attempt is None


def test_attempt_history_is_sequence_like_and_copies_input_iterable() -> None:
    first = Attempt(
        request="first-request",
        raw_output={"raw": 1},
        output="first-output",
        failure=None,
        attempt_number=1,
    )
    second = Attempt(
        request="second-request",
        raw_output={"raw": 2},
        output=None,
        failure=TerminalFailure("bad schema"),
        attempt_number=2,
    )
    source_attempts = [first, second]

    history = AttemptHistory(source_attempts, max_attempts=3)
    source_attempts.clear()

    assert len(history) == 2
    assert history[0] is first
    assert history[1] is second
    assert history.last_attempt is second
    assert history[1:] == (second,)


def test_run_result_holds_history_and_final_failure() -> None:
    failure = TerminalFailure("give up")
    attempt = Attempt(
        request="request",
        raw_output={"raw": 1},
        output=None,
        failure=failure,
        attempt_number=1,
    )
    history = AttemptHistory([attempt], max_attempts=1)

    result = RunResult(
        output=None,
        raw_output={"raw": 1},
        last_request="request",
        history=history,
        final_failure=failure,
        exhausted=False,
    )

    assert result.history is history
    assert result.final_failure is failure
    assert result.output is None
    assert result.raw_output == {"raw": 1}
    assert result.last_request == "request"
    assert result.exhausted is False
