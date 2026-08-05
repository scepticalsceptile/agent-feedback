"""Public controlled failure types."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ApplyFeedback = Callable[..., Any]


class RetryableFailure(Exception):
    """Signals a retry should happen if attempts remain."""

    def __init__(
        self,
        message: str,
        *,
        feedback: Any,
        apply_feedback: ApplyFeedback | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.feedback = feedback
        self.apply_feedback = apply_feedback
        self.metadata = None if metadata is None else dict(metadata)


class TerminalFailure(Exception):
    """Signals the loop should stop immediately."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


__all__ = ["ApplyFeedback", "RetryableFailure", "TerminalFailure"]
