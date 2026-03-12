"""Tool and ToolResult data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class Tool:
    """Describes a callable tool with its JSON Schema.

    Args:
        name: Unique tool identifier.
        description: Human-readable description for the LLM.
        fn: The async callable to execute.
        schema: JSON Schema for the function parameters.
        requires_approval: If True, the runtime will call
            ``AgentCallback.on_approval_request`` before executing
            this tool. Execution is skipped if any callback returns
            False.  Defaults to False.
    """

    name: str
    description: str
    fn: Callable[..., Any]
    schema: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Format for Anthropic's tools parameter."""
        return {
            'name': self.name,
            'description': self.description,
            'input_schema': self.schema,
        }

    def to_openai_schema(self) -> dict[str, Any]:
        """Format for OpenAI's tools parameter."""
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': self.schema,
            },
        }

    def to_gemini_schema(self) -> dict[str, Any]:
        """Format for Gemini's tools parameter."""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.schema,
        }


@dataclass(slots=True)
class ToolResult:
    """Result of a single tool execution.

    Args:
        call_id: Provider-assigned tool call identifier.
        name: Name of the tool that was called.
        success: Whether the execution succeeded.
        output: Stringified output on success, None on failure.
        error: Error message on failure, None on success.
    """

    call_id: str
    name: str
    success: bool
    output: str | None = None
    error: str | None = None
