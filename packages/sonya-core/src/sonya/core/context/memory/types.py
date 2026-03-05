"""Normalized message types for cross-provider context transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    """Provider-agnostic message representation.

    Args:
        role: Message role ('user', 'assistant', 'system', 'tool').
        content: Plain text content.
        tool_calls: Normalized tool call dicts.
        tool_results: Normalized tool result dicts.
        metadata: Extra metadata (agent_name, provider, etc).
    """

    role: str
    content: str
    tool_calls: list[dict[str, Any]] = field(
        default_factory=list
    )
    tool_results: list[dict[str, Any]] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@runtime_checkable
class MemoryPipeline(Protocol):
    """Protocol for cross-provider message transformation.

    Implementations live in the sonya-pipeline package.
    sonya-core defines only the interface.
    """

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        """Normalize provider-native history to generic form."""
        ...

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        """Reconstruct normalized messages to provider-native form."""
        ...
