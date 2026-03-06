"""Structured log event dataclasses."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


def _now() -> float:
    """Return monotonic timestamp in seconds."""
    return time.monotonic()


@dataclass(frozen=True, slots=True)
class LogEvent:
    """Base log event.

    Args:
        event_type: Identifier string for the event kind.
        timestamp: Monotonic timestamp when the event was created.
    """

    event_type: str
    timestamp: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class LLMRequestEvent(LogEvent):
    """Emitted before an LLM request is sent.

    Args:
        model: Model identifier.
        message_count: Number of messages in the request.
        kwargs_keys: Keys of additional kwargs passed.
    """

    event_type: str = field(default='llm_request', init=False)
    model: str = ''
    message_count: int = 0
    kwargs_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LLMResponseEvent(LogEvent):
    """Emitted after an LLM response is received.

    Args:
        model: Model identifier.
        stop_reason: Why the model stopped generating.
        latency_ms: Round-trip time in milliseconds.
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.
    """

    event_type: str = field(default='llm_response', init=False)
    model: str = ''
    stop_reason: str | None = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class IterationEvent(LogEvent):
    """Emitted at the start or end of an agent loop iteration.

    Args:
        agent_name: Name of the agent.
        iteration: Zero-based iteration index.
        phase: Either 'start' or 'end'.
    """

    event_type: str = field(default='iteration', init=False)
    agent_name: str = ''
    iteration: int = 0
    phase: str = 'start'


@dataclass(frozen=True, slots=True)
class ToolExecutionEvent(LogEvent):
    """Emitted after a tool finishes execution.

    Args:
        agent_name: Name of the agent that invoked the tool.
        tool_name: Name of the tool.
        arguments: Arguments passed to the tool.
        output_preview: First 200 chars of the tool output.
        success: Whether the execution succeeded.
        error: Error message on failure.
        duration_ms: Execution time in milliseconds.
    """

    event_type: str = field(default='tool_execution', init=False)
    agent_name: str = ''
    tool_name: str = ''
    arguments: tuple[tuple[str, str], ...] = ()
    output_preview: str = ''
    success: bool = True
    error: str | None = None
    duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class HandoffEvent(LogEvent):
    """Emitted when a handoff occurs between agents.

    Args:
        from_agent: Source agent name.
        to_agent: Target agent name.
    """

    event_type: str = field(default='handoff', init=False)
    from_agent: str = ''
    to_agent: str = ''


@dataclass(frozen=True, slots=True)
class AgentStartEvent(LogEvent):
    """Emitted when an agent begins execution via Runner.

    Args:
        agent_name: Name of the agent.
        message_count: Number of messages passed to the agent.
    """

    event_type: str = field(default='agent_start', init=False)
    agent_name: str = ''
    message_count: int = 0


@dataclass(frozen=True, slots=True)
class AgentEndEvent(LogEvent):
    """Emitted when an agent finishes execution via Runner.

    Args:
        agent_name: Name of the agent.
        text_preview: First 200 chars of the final text.
        has_handoff: Whether the result includes a handoff.
    """

    event_type: str = field(default='agent_end', init=False)
    agent_name: str = ''
    text_preview: str = ''
    has_handoff: bool = False
