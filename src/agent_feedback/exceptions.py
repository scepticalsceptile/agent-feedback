"""Exceptions for the agent_feedback library."""

from __future__ import annotations

from ._failures import RetryableFailure


class AgentFeedbackError(Exception):
    """Base class for library-defined exceptions."""


class MissingApplyFeedbackError(AgentFeedbackError):
    """Raised when a retryable failure has no apply_feedback path."""


class ExhaustedRetriesError(AgentFeedbackError):
    """Raised when the convenience API exhausts all retry attempts."""

    def __init__(self, *, attempts: int, last_failure: RetryableFailure) -> None:
        attempt_label = "attempt" if attempts == 1 else "attempts"
        message = (
            f"Retries exhausted after {attempts} {attempt_label}. "
            f"Last retryable failure: {last_failure.message}"
        )
        super().__init__(message)
        self.message = message
        self.attempts = attempts
        self.last_failure = last_failure


__all__ = [
    "AgentFeedbackError",
    "ExhaustedRetriesError",
    "MissingApplyFeedbackError",
]