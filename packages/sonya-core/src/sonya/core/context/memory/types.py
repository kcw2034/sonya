"""Normalized message types for cross-provider context transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
