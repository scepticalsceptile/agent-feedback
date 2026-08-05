"""Smoke tests for the public package surface."""

from __future__ import annotations

import agent_feedback


def test_package_exposes_version() -> None:
	assert agent_feedback.__version__ == "0.1.0"


def test_package_exports_public_symbols() -> None:
	assert hasattr(agent_feedback, "Attempt")
	assert hasattr(agent_feedback, "AttemptHistory")
	assert hasattr(agent_feedback, "Request")
	assert hasattr(agent_feedback, "RetryableFailure")
	assert hasattr(agent_feedback, "Runner")
	assert hasattr(agent_feedback, "RunResult")
	assert hasattr(agent_feedback, "TerminalFailure")
	assert hasattr(agent_feedback, "arun")
	assert hasattr(agent_feedback, "arun_full")
	assert agent_feedback.__all__ == [
		"__version__",
		"Attempt",
		"AttemptHistory",
		"Request",
		"RetryableFailure",
		"Runner",
		"RunResult",
		"TerminalFailure",
		"arun",
		"arun_full",
	]
