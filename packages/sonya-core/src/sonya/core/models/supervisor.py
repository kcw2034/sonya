"""SupervisorRuntime — a supervisor agent that delegates to workers."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sonya.core.utils.tool_context import ToolContext
from sonya.core.utils.handoff import _instructions_preview

from .agent_runtime import AgentRuntime
from .tool import Tool

if TYPE_CHECKING:
    from .agent import Agent, AgentResult


@dataclass(slots=True)
class SupervisorConfig:
    """Configuration for a supervisor runtime.

    Args:
        supervisor: The supervisor agent that decides delegation.
        workers: List of worker agents the supervisor can call.
        max_iterations: Maximum supervisor loop iterations.
        context: Shared tool context across all agents.
    """

    supervisor: Agent
    workers: list[Agent] = field(default_factory=list)
    max_iterations: int = 10
    context: ToolContext | None = None


def _make_worker_tool(
    worker: Agent,
    context: ToolContext | None = None,
) -> Tool:
    """Create a tool that runs *worker* and returns its result.

    The supervisor agent sees each worker as a callable tool, allowing
    it to delegate sub-tasks naturally.

    Args:
        worker: The worker agent to wrap.
        context: Shared tool context.

    Returns:
        A :class:`Tool` whose execution runs the full worker agent.
    """

    async def _run_worker(task: str) -> str:
        """Execute the worker agent with the given task."""
        runtime = AgentRuntime(worker, context=context)
        messages = [{'role': 'user', 'content': task}]
        result = await runtime.run(messages)
        return result.text

    return Tool(
        name=f'ask_{worker.name}',
        description=(
            f'Delegate a task to the "{worker.name}" '
            f'agent. '
            f'{_instructions_preview(worker.instructions)}'
        ),
        fn=_run_worker,
        schema={
            'type': 'object',
            'properties': {
                'task': {
                    'type': 'string',
                    'description': (
                        'The task description to send '
                        'to the worker.'
                    ),
                },
            },
            'required': ['task'],
        },
    )


class SupervisorRuntime:
    """Runs a supervisor agent with worker agents as callable tools.

    The supervisor sees each worker as a tool it can invoke. When the
    supervisor calls a worker tool, the worker runs its own full
    agent loop and returns the result.

    Args:
        config: :class:`SupervisorConfig` with supervisor and workers.
    """

    def __init__(self, config: SupervisorConfig) -> None:
        self._config = config
        self._context = config.context or ToolContext()

        # Build worker tools and inject them into a shallow copy of
        # the supervisor agent, leaving the original agent untouched.
        # This prevents tool accumulation when the same agent instance
        # is reused across multiple SupervisorRuntime objects.
        worker_tools = [
            _make_worker_tool(w, self._context)
            for w in config.workers
        ]
        self._supervisor = dataclasses.replace(
            config.supervisor,
            tools=list(config.supervisor.tools) + worker_tools,
        )

    async def run(
        self,
        messages: list[dict[str, Any]],
    ) -> AgentResult:
        """Execute the supervisor agent.

        Args:
            messages: Initial conversation messages.

        Returns:
            :class:`AgentResult` from the supervisor.
        """
        runtime = AgentRuntime(
            self._supervisor,
            context=self._context,
        )
        return await runtime.run(messages)
