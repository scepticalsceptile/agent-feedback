"""Exceptions for the agent_feedback library."""

from __future__ import annotations


class AgentFeedbackError(Exception):
    """Base class for library-defined exceptions."""


class MissingApplyFeedbackError(AgentFeedbackError):
    """Raised when a retryable failure has no apply_feedback path."""


__all__ = ["AgentFeedbackError", "MissingApplyFeedbackError"]