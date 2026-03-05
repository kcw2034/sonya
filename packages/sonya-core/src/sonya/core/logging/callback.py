"""DebugCallback — unified agent + runner lifecycle logger."""

from __future__ import annotations

import json
import logging
from typing import Any

from sonya.core.agent.types import AgentResult
from sonya.core.logging.events import (
    AgentEndEvent,
    AgentStartEvent,
    HandoffEvent,
    IterationEvent,
    ToolExecutionEvent,
)

_logger = logging.getLogger('sonya.agent')


class DebugCallback:
    """Callback that logs agent and runner lifecycle events.

    Implements both AgentCallback and RunnerCallback protocols
    so it can be used with Agent.callbacks and RunnerConfig.callbacks.

    Args:
        level: Logging level (default: DEBUG).
        log_json: If True, emit structured JSON log lines.
    """

    def __init__(
        self,
        level: int = logging.DEBUG,
        log_json: bool = False,
    ) -> None:
        self._level = level
        self._log_json = log_json

    # --- AgentCallback methods ---

    async def on_iteration_start(
        self,
        agent_name: str,
        iteration: int,
    ) -> None:
        """Log the start of an agent loop iteration."""
        event = IterationEvent(
            agent_name=agent_name,
            iteration=iteration,
            phase='start',
        )
        self._emit_text(
            '[Iteration Start] agent=%s iteration=%d',
            agent_name,
            iteration,
            event=event,
        )

    async def on_iteration_end(
        self,
        agent_name: str,
        iteration: int,
    ) -> None:
        """Log the end of an agent loop iteration."""
        event = IterationEvent(
            agent_name=agent_name,
            iteration=iteration,
            phase='end',
        )
        self._emit_text(
            '[Iteration End] agent=%s iteration=%d',
            agent_name,
            iteration,
            event=event,
        )

    async def on_tool_start(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Log the start of a tool execution."""
        self._emit_text(
            '[Tool Start] agent=%s tool=%s',
            agent_name,
            tool_name,
        )

    async def on_tool_end(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        output: str | None,
        error: str | None,
        success: bool,
        duration_ms: float = 0.0,
    ) -> None:
        """Log the result of a tool execution."""
        preview = (output or '')[:200]
        frozen_args = tuple(
            (str(k), str(v)) for k, v in arguments.items()
        )
        event = ToolExecutionEvent(
            agent_name=agent_name,
            tool_name=tool_name,
            arguments=frozen_args,
            output_preview=preview,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )
        status = 'OK' if success else 'FAIL'
        msg = (
            f'[Tool {status}] agent={agent_name} '
            f'tool={tool_name}'
        )
        if duration_ms:
            msg += f' duration={duration_ms:.0f}ms'
        if error:
            msg += f' error={error}'
        self._emit_text(msg, event=event)

    async def on_handoff(
        self,
        from_agent: str,
        to_agent: str,
    ) -> None:
        """Log a handoff between agents."""
        event = HandoffEvent(
            from_agent=from_agent,
            to_agent=to_agent,
        )
        self._emit_text(
            '[Handoff] from=%s to=%s',
            from_agent,
            to_agent,
            event=event,
        )

    # --- RunnerCallback methods ---

    async def on_agent_start(
        self,
        agent_name: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """Log when a Runner starts an agent."""
        event = AgentStartEvent(
            agent_name=agent_name,
            message_count=len(messages),
        )
        self._emit_text(
            '[Agent Start] agent=%s messages=%d',
            agent_name,
            len(messages),
            event=event,
        )

    async def on_agent_end(
        self,
        result: AgentResult,
    ) -> None:
        """Log when a Runner finishes an agent."""
        event = AgentEndEvent(
            agent_name=result.agent_name,
            text_preview=(result.text or '')[:200],
            has_handoff=result.handoff_to is not None,
        )
        self._emit_text(
            '[Agent End] agent=%s has_handoff=%s',
            result.agent_name,
            result.handoff_to is not None,
            event=event,
        )

    # --- internal ---

    def _emit_text(
        self,
        fmt: str,
        *args: Any,
        event: Any = None,
    ) -> None:
        """Log in human-readable or JSON format."""
        if self._log_json and event is not None:
            data: dict[str, Any] = {
                'event': event.event_type,
                'timestamp': event.timestamp,
            }
            for f in event.__dataclass_fields__:
                if f not in ('event_type', 'timestamp'):
                    val = getattr(event, f)
                    if isinstance(val, tuple):
                        val = dict(val)
                    data[f] = val
            _logger.log(self._level, json.dumps(data))
        else:
            _logger.log(self._level, fmt, *args)
