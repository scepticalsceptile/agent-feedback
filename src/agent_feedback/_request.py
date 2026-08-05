"""Public request envelope types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, init=False, slots=True)
class Request:
    """Explicit envelope for invoke call signatures.

    Bare requests stay bare. This wrapper exists for the exact-call case where
    an invoke function should receive positional and keyword arguments directly.
    """

    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        object.__setattr__(self, "args", tuple(args))
        object.__setattr__(self, "kwargs", dict(kwargs))


__all__ = ["Request"]
