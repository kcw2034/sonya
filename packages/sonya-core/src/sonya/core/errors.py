"""Shared error types for tools and agents."""

from __future__ import annotations


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
