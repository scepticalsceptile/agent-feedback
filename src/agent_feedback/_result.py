"""Run result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._history import AttemptHistory


@dataclass(frozen=True, slots=True)
class RunResult:
    """Structured result returned by the full async API."""

    output: Any | None
    raw_output: Any | None
    last_request: Any
    history: AttemptHistory
    final_failure: Exception | None
    exhausted: bool


__all__ = ["RunResult"]
