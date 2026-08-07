"""Core async runner implementation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ._callbacks import call_apply_feedback, call_extract, call_validator
from ._failures import ApplyFeedback, RetryableFailure, TerminalFailure
from ._history import Attempt, AttemptHistory
from ._invoke import invoke_request
from ._result import RunResult
from .exceptions import MissingApplyFeedbackError


class _UnsetType:
    """Sentinel type for omitted Runner method overrides."""


_UNSET = _UnsetType()


def _history_snapshot(attempts: list[Attempt], *, max_attempts: int) -> AttemptHistory:
    """Build an immutable history snapshot from the recorded attempts."""

    return AttemptHistory(attempts, max_attempts=max_attempts)


def _identity_extract(response: Any) -> Any:
    """Return the raw response unchanged for the default extract path."""

    return response


def _resolve_runner_override(override: Any, default: Any) -> Any:
    """Use the Runner default when the call-site override was omitted."""

    if override is _UNSET:
        return default

    return override


async def _build_next_request(
    *,
    error: RetryableFailure,
    request: Any,
    history: AttemptHistory,
    apply_feedback: ApplyFeedback | None,
) -> Any:
    """Resolve the next request after a retryable failure."""

    resolved_apply_feedback = error.apply_feedback or apply_feedback

    if resolved_apply_feedback is None:
        raise MissingApplyFeedbackError(
            "RetryableFailure requires an apply_feedback path from either the "
            "failure or the arun_full(...) call."
        ) from error

    return await call_apply_feedback(
        resolved_apply_feedback,
        error.feedback,
        request,
        error,
        history,
    )


async def arun_full(
    *,
    request: Any,
    invoke: Callable[..., Any],
    extract: Callable[..., Any] = _identity_extract,
    validators: Sequence[Callable[..., Any]] = (),
    apply_feedback: ApplyFeedback | None = None,
    max_attempts: int = 3,
) -> RunResult:
    """Run the full invoke, extract, validate, and retry loop."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    attempts: list[Attempt] = []
    current_request = request
    last_raw_output: Any | None = None
    last_output: Any | None = None

    for attempt_number in range(1, max_attempts + 1):
        history = _history_snapshot(attempts, max_attempts=max_attempts)
        last_raw_output = None
        last_output = None

        try:
            last_raw_output = await invoke_request(invoke, current_request)
            last_output = await call_extract(
                extract,
                last_raw_output,
                current_request,
                history,
            )

            for validator in validators:
                await call_validator(validator, last_output, history)
        except RetryableFailure as error:
            attempts.append(
                Attempt(
                    request=current_request,
                    raw_output=last_raw_output,
                    output=last_output,
                    failure=error,
                    attempt_number=attempt_number,
                )
            )

            if attempt_number == max_attempts:
                return RunResult(
                    output=last_output,
                    raw_output=last_raw_output,
                    last_request=current_request,
                    history=_history_snapshot(attempts, max_attempts=max_attempts),
                    final_failure=error,
                    exhausted=True,
                )

            current_request = await _build_next_request(
                error=error,
                request=current_request,
                history=_history_snapshot(attempts, max_attempts=max_attempts),
                apply_feedback=apply_feedback,
            )
            continue
        except TerminalFailure as error:
            attempts.append(
                Attempt(
                    request=current_request,
                    raw_output=last_raw_output,
                    output=last_output,
                    failure=error,
                    attempt_number=attempt_number,
                )
            )
            return RunResult(
                output=last_output,
                raw_output=last_raw_output,
                last_request=current_request,
                history=_history_snapshot(attempts, max_attempts=max_attempts),
                final_failure=error,
                exhausted=False,
            )

        attempts.append(
            Attempt(
                request=current_request,
                raw_output=last_raw_output,
                output=last_output,
                failure=None,
                attempt_number=attempt_number,
            )
        )
        return RunResult(
            output=last_output,
            raw_output=last_raw_output,
            last_request=current_request,
            history=_history_snapshot(attempts, max_attempts=max_attempts),
            final_failure=None,
            exhausted=False,
        )

    raise AssertionError("arun_full reached an unexpected state.")


async def arun(
    *,
    request: Any,
    invoke: Callable[..., Any],
    extract: Callable[..., Any] = _identity_extract,
    validators: Sequence[Callable[..., Any]] = (),
    apply_feedback: ApplyFeedback | None = None,
    max_attempts: int = 3,
    on_exhausted_retries: Literal["raise", "return_last"] = "raise",
) -> Any:
    """Run the convenience API that returns extracted output or raises."""

    result = await arun_full(
        invoke=invoke,
        request=request,
        extract=extract,
        validators=validators,
        apply_feedback=apply_feedback,
        max_attempts=max_attempts,
    )

    if result.final_failure is None:
        return result.output

    if isinstance(result.final_failure, TerminalFailure):
        raise result.final_failure

    if result.exhausted:
        if on_exhausted_retries == "return_last":
            return result.output

        raise result.final_failure

    raise AssertionError("arun reached an unexpected state.")


@dataclass(frozen=True, init=False, slots=True)
class Runner:
    """Reusable convenience wrapper around the function entry points."""

    invoke: Callable[..., Any]
    extract: Callable[..., Any]
    validators: tuple[Callable[..., Any], ...]
    apply_feedback: ApplyFeedback | None
    max_attempts: int
    on_exhausted_retries: Literal["raise", "return_last"]

    def __init__(
        self,
        *,
        invoke: Callable[..., Any],
        extract: Callable[..., Any] = _identity_extract,
        validators: Sequence[Callable[..., Any]] = (),
        apply_feedback: ApplyFeedback | None = None,
        max_attempts: int = 3,
        on_exhausted_retries: Literal["raise", "return_last"] = "raise",
    ) -> None:
        object.__setattr__(self, "invoke", invoke)
        object.__setattr__(self, "extract", extract)
        object.__setattr__(self, "validators", tuple(validators))
        object.__setattr__(self, "apply_feedback", apply_feedback)
        object.__setattr__(self, "on_exhausted_retries", on_exhausted_retries)
        object.__setattr__(self, "max_attempts", max_attempts)

    async def arun(
        self,
        *,
        request: Any,
        extract: Any = _UNSET,
        validators: Any = _UNSET,
        apply_feedback: Any = _UNSET,
        max_attempts: Any = _UNSET,
        on_exhausted_retries: Any = _UNSET,
    ) -> Any:
        """Run the convenience API using Runner defaults plus per-call overrides."""

        return await arun(
            request=request,
            invoke=self.invoke,
            extract=_resolve_runner_override(extract, self.extract),
            validators=_resolve_runner_override(validators, self.validators),
            apply_feedback=_resolve_runner_override(
                apply_feedback,
                self.apply_feedback,
            ),
            max_attempts=_resolve_runner_override(max_attempts, self.max_attempts),
            on_exhausted_retries=_resolve_runner_override(
                on_exhausted_retries,
                self.on_exhausted_retries,
            ),
        )

    async def arun_full(
        self,
        *,
        request: Any,
        extract: Any = _UNSET,
        validators: Any = _UNSET,
        apply_feedback: Any = _UNSET,
        max_attempts: Any = _UNSET,
    ) -> RunResult:
        """Run the structured API using Runner defaults plus per-call overrides."""

        return await arun_full(
            invoke=self.invoke,
            request=request,
            extract=_resolve_runner_override(extract, self.extract),
            validators=_resolve_runner_override(validators, self.validators),
            apply_feedback=_resolve_runner_override(
                apply_feedback,
                self.apply_feedback,
            ),
            max_attempts=_resolve_runner_override(max_attempts, self.max_attempts),
        )


__all__ = ["Runner", "arun", "arun_full"]
