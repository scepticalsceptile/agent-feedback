"""History model types."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, overload


@dataclass(frozen=True, slots=True)
class Attempt:
    """One recorded invoke/extract/validate attempt."""

    request: Any
    raw_output: Any | None
    output: Any | None
    failure: Exception | None
    attempt_number: int


@dataclass(frozen=True, init=False, slots=True)
class AttemptHistory(Sequence[Attempt]):
    """Immutable audit trail for attempts."""

    max_attempts: int
    attempts: tuple[Attempt, ...]

    def __init__(self, attempts: Iterable[Attempt] = (), *, max_attempts: int) -> None:
        object.__setattr__(self, "max_attempts", max_attempts)
        object.__setattr__(self, "attempts", tuple(attempts))

    @property
    def last_attempt(self) -> Attempt | None:
        if not self.attempts:
            return None

        return self.attempts[-1]

    @overload
    def __getitem__(self, index: int) -> Attempt: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Attempt, ...]: ...

    def __getitem__(self, index: int | slice) -> Attempt | tuple[Attempt, ...]:
        return self.attempts[index]

    def __len__(self) -> int:
        return len(self.attempts)


__all__ = ["Attempt", "AttemptHistory"]
