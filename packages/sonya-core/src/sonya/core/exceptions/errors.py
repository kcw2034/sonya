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


class GuardrailError(AgentError):
    """Raised when an agent exceeds a configured guardrail limit.

    Args:
        agent_name: Name of the agent that breached the limit.
        reason: Human-readable description of the violated limit.
    """

    def __init__(self, agent_name: str, reason: str) -> None:
        self.reason = reason
        super().__init__(agent_name, f'Guardrail: {reason}')


class ToolApprovalDeniedError(AgentError):
    """Raised when a tool execution is blocked by an approval callback.

    This error is available for callers who wish to detect a denial
    explicitly. The AgentRuntime itself does NOT raise this — it feeds
    the denial back to the LLM as a tool error result instead.

    Args:
        agent_name: Name of the agent whose tool was denied.
        tool_name: Name of the tool that was denied approval.
    """

    def __init__(self, agent_name: str, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(
            agent_name,
            f"Tool '{tool_name}' approval denied by callback",
        )
