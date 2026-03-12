"""Shared error types for tools and agents."""

from __future__ import annotations


class MaxRetriesExceededError(Exception):
    """Raised when all retry attempts for a provider call are exhausted.

    Args:
        attempts: Total number of attempts made (including initial).
        last_error: The exception from the final attempt.
    """

    def __init__(
        self,
        attempts: int,
        last_error: Exception,
    ) -> None:
        self.attempts = attempts
        super().__init__(
            f'All {attempts} attempt(s) failed. '
            f'Last error: {type(last_error).__name__}: {last_error}'
        )


class ToolError(Exception):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f'Tool "{tool_name}" failed: {message}')


class AgentError(Exception):
    """Raised when an agent execution fails."""

    def __init__(self, agent_name: str, message: str) -> None:
        self.agent_name = agent_name
        super().__init__(f'Agent "{agent_name}" failed: {message}')
