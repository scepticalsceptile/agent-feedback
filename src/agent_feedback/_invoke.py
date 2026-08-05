"""Internal request invocation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._callbacks import await_if_needed
from ._request import Request


async def invoke_request(invoke: Callable[..., Any], request: Any) -> Any:
    """Invoke the current request using the documented request families."""

    if isinstance(request, Request):
        return await await_if_needed(invoke(*request.args, **request.kwargs))

    return await await_if_needed(invoke(request))


__all__ = ["invoke_request"]
