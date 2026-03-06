"""Agent and AgentResult data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sonya.core.client.base import BaseClient
from sonya.core.models.tool import Tool
from sonya.core.schemas.types import AgentCallback


@dataclass(slots=True)
class Agent:
    """Describes an autonomous agent that can use tools and hand off.

    Args:
        name: Unique agent identifier.
        client: LLM client to use for generation.
        instructions: System prompt for the agent.
        tools: List of tools available to the agent.
        handoffs: List of agents this agent can hand off to.
        max_iterations: Maximum LLM <-> tool loop iterations.
        callbacks: Agent lifecycle callbacks.
    """

    name: str
    client: BaseClient
    instructions: str = ''
    tools: list[Tool] = field(default_factory=list)
    handoffs: list[Agent] = field(default_factory=list)
    max_iterations: int = 10
    callbacks: list[AgentCallback] = field(
        default_factory=list
    )


@dataclass(slots=True)
class AgentResult:
    """Result returned after an agent completes execution.

    Args:
        agent_name: Name of the agent that produced this result.
        text: Final text response from the agent.
        history: Full message history of the agent run.
        handoff_to: Name of the agent to hand off to, if any.
        metadata: Optional metadata from the run.
    """

    agent_name: str
    text: str
    history: list[dict[str, Any]] = field(
        default_factory=list
    )
    handoff_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
