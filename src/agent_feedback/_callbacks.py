"""Internal callback invocation helpers."""

from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, isawaitable, signature
from typing import Any

from ._history import AttemptHistory

_POSITIONAL_PARAMETER_KINDS = {
    Parameter.POSITIONAL_ONLY,
    Parameter.POSITIONAL_OR_KEYWORD,
}


async def await_if_needed(value: Any) -> Any:
    """Await the value when it is awaitable, otherwise return it directly."""

    if isawaitable(value):
        return await value

    return value


def _callback_arity(
    callback: Callable[..., Any],
    *,
    callback_name: str,
    supported_arities: tuple[int, ...],
) -> int:
    """Return the supported positional arity for a user callback."""

    try:
        callback_signature = signature(callback)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Could not inspect {callback_name} callback signature."
        ) from exc

    positional_count = 0

    for parameter in callback_signature.parameters.values():
        if parameter.kind in _POSITIONAL_PARAMETER_KINDS:
            positional_count += 1
            continue

        if parameter.kind is Parameter.VAR_POSITIONAL:
            raise _unsupported_callback_shape(
                callback_name=callback_name,
                supported_arities=supported_arities,
            )

        if (
            parameter.kind is Parameter.KEYWORD_ONLY
            and parameter.default is Parameter.empty
        ):
            raise _unsupported_callback_shape(
                callback_name=callback_name,
                supported_arities=supported_arities,
            )

    if positional_count not in supported_arities:
        raise _unsupported_callback_shape(
            callback_name=callback_name,
            supported_arities=supported_arities,
        )

    return positional_count


def _unsupported_callback_shape(
    *, callback_name: str, supported_arities: tuple[int, ...]
) -> TypeError:
    """Build the shared TypeError for unsupported callback signatures."""

    supported = ", ".join(str(arity) for arity in supported_arities)
    return TypeError(
        f"{callback_name} callback must accept exactly {supported} positional "
        "arguments, with no *args and no required keyword-only parameters."
    )


async def call_extract(
    extract: Callable[..., Any],
    raw_output: Any,
    request: Any,
    history: AttemptHistory,
) -> Any:
    """Call the extract callback with one of the documented response-first shapes."""

    arity = _callback_arity(
        extract,
        callback_name="extract",
        supported_arities=(1, 2, 3),
    )

    if arity == 1:
        return await await_if_needed(extract(raw_output))

    if arity == 2:
        return await await_if_needed(extract(raw_output, request))

    return await await_if_needed(extract(raw_output, request, history))


async def call_validator(
    validator: Callable[..., Any],
    output: Any,
    history: AttemptHistory,
) -> None:
    """Call the validator callback and enforce the None-on-success rule."""

    arity = _callback_arity(
        validator,
        callback_name="validator",
        supported_arities=(1, 2),
    )

    if arity == 1:
        result = await await_if_needed(validator(output))
    else:
        result = await await_if_needed(validator(output, history))

    if result is not None:
        raise TypeError(
            "validator callback must return None on success; raise "
            "RetryableFailure or TerminalFailure to signal failure."
        )


async def call_apply_feedback(
    apply_feedback: Callable[..., Any],
    feedback: Any,
    request: Any,
    error: Exception,
    history: AttemptHistory,
) -> Any:
    """Call the apply_feedback callback with one of the documented shapes."""

    arity = _callback_arity(
        apply_feedback,
        callback_name="apply_feedback",
        supported_arities=(2, 3, 4),
    )

    if arity == 2:
        return await await_if_needed(apply_feedback(feedback, request))

    if arity == 3:
        return await await_if_needed(apply_feedback(feedback, request, error))

    return await await_if_needed(apply_feedback(feedback, request, error, history))


__all__ = [
    "await_if_needed",
    "call_apply_feedback",
    "call_extract",
    "call_validator",
]
