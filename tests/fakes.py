"""Shared fake objects for the test suite.

These fakes stay deliberately small and readable so later loop tests can focus
on harness behavior instead of mock wiring.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SemanticRequest:
	"""Small custom request object for tests that should not use plain strings."""

	prompt: str
	system: str | None = None


@dataclass(frozen=True, slots=True)
class FakeRawResponse:
	"""Simple raw output object that forces extraction to inspect a field."""

	text: str
	tool_calls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InvocationCall:
	"""Recorded invoke call arguments."""

	args: tuple[Any, ...]
	kwargs: dict[str, Any]


class SequenceInvokable:
	"""Async invokable that returns or raises from a scripted sequence."""

	def __init__(self, steps: Iterable[Any | BaseException]) -> None:
		self._steps = list(steps)
		self._next_index = 0
		self.calls: list[InvocationCall] = []

	@property
	def call_count(self) -> int:
		return len(self.calls)

	async def __call__(self, *args: Any, **kwargs: Any) -> Any:
		self.calls.append(InvocationCall(args=args, kwargs=dict(kwargs)))

		if self._next_index >= len(self._steps):
			raise AssertionError("SequenceInvokable ran out of scripted steps.")

		step = self._steps[self._next_index]
		self._next_index += 1

		if isinstance(step, BaseException):
			raise step

		return step


class EchoInvokable:
	"""Async invokable that returns the request or a trivial derivative."""

	def __init__(self, transform: Callable[..., Any] | None = None) -> None:
		self._transform = transform
		self.calls: list[InvocationCall] = []

	@property
	def call_count(self) -> int:
		return len(self.calls)

	async def __call__(self, *args: Any, **kwargs: Any) -> Any:
		call = InvocationCall(args=args, kwargs=dict(kwargs))
		self.calls.append(call)

		if self._transform is not None:
			return self._transform(*args, **kwargs)

		if kwargs:
			return {"args": args, "kwargs": dict(kwargs)}

		if len(args) == 1:
			return args[0]

		return args


class FailingInvokable:
	"""Async invokable that raises the same known exception on every call."""

	def __init__(self, error: BaseException) -> None:
		self.error = error
		self.calls: list[InvocationCall] = []

	@property
	def call_count(self) -> int:
		return len(self.calls)

	async def __call__(self, *args: Any, **kwargs: Any) -> Any:
		self.calls.append(InvocationCall(args=args, kwargs=dict(kwargs)))
		raise self.error


__all__ = [
	"EchoInvokable",
	"FailingInvokable",
	"FakeRawResponse",
	"InvocationCall",
	"SemanticRequest",
	"SequenceInvokable",
]

