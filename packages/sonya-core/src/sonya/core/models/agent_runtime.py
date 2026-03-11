"""AgentRuntime — the LLM <-> tool execution loop."""

from __future__ import annotations

from typing import Any

from sonya.core.parsers.adapter import _get_adapter
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.exceptions.errors import AgentError
from sonya.core.utils.tool_context import ToolContext
from sonya.core.models.tool_registry import ToolRegistry
from sonya.core.utils.handoff import _HANDOFF_PREFIX


class AgentRuntime:
    """Runs a single agent through its generate-parse-execute loop.

    The runtime:
    1. Builds the tool registry (agent tools + handoff tools).
    2. Calls the LLM with the system prompt, history, and tool schemas.
    3. Parses the response via the appropriate adapter.
    4. Executes any tool calls and feeds results back.
    5. Repeats until the LLM stops or max_iterations is reached.
    6. Detects handoff tool calls and signals the orchestrator.

    Args:
        agent: The :class:`Agent` to run.
        context: Optional shared :class:`ToolContext`.
    """

    def __init__(
        self,
        agent: Agent,
        context: ToolContext | None = None,
    ) -> None:
        self._agent = agent
        self._context = context or ToolContext()
        self._adapter = _get_adapter(agent.client)
        self._registry = self._build_registry()
        self._callbacks = agent.callbacks

    def _build_registry(self) -> ToolRegistry:
        """Create a registry containing agent tools and handoff tools."""
        from sonya.core.utils.handoff import (
            _make_handoff_tool,
        )

        registry = ToolRegistry()
        for t in self._agent.tools:
            registry.register(t)
        for target in self._agent.handoffs:
            registry.register(_make_handoff_tool(target))
        return registry

    async def run(
        self,
        messages: list[dict[str, Any]],
        prompt_context: dict[str, str] | None = None,
    ) -> AgentResult:
        """Execute the agent loop starting from *messages*.

        Args:
            messages: Initial conversation messages
                (user turn, etc).
            prompt_context: Template variables passed to
                :meth:`Prompt.render` when *instructions*
                is a :class:`Prompt`.

        Returns:
            :class:`AgentResult` with the final text and
            history.

        Raises:
            AgentError: If the loop exceeds max_iterations.
        """
        agent = self._agent
        adapter = self._adapter
        registry = self._registry
        history = list(messages)

        # Resolve instructions
        from sonya.core.models.prompt import Prompt

        instructions = agent.instructions
        if isinstance(instructions, Prompt):
            instructions = instructions.render(
                **(prompt_context or {})
            )

        # Build generate kwargs via adapter
        tools = registry.tools
        schemas: list[dict[str, Any]] | None = None
        if tools:
            provider_name = type(agent.client).__name__
            _provider_map = {
                'AnthropicClient': 'anthropic',
                'OpenAIClient': 'openai',
                'GeminiClient': 'gemini',
            }
            provider = _provider_map.get(
                provider_name, 'openai'
            )
            schemas = registry.schemas(provider)

        gen_kwargs = adapter.format_generate_kwargs(
            instructions, schemas
        )

        # Extract system message for OpenAI-style injection.
        # Strip any pre-existing system messages from history to
        # ensure the agent's instructions are the sole system
        # message and avoid duplicates when history is passed
        # from a previous agent (e.g. via Runner handoff).
        system_message = gen_kwargs.pop(
            '_system_message', None
        )
        if system_message:
            history = [
                m for m in history
                if m.get('role') != 'system'
            ]
            history = [
                {'role': 'system', 'content': system_message}
            ] + history

        for _iteration in range(agent.max_iterations):
            # Callback: iteration start
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_iteration_start'):
                        await cb.on_iteration_start(
                            agent.name, _iteration,
                        )

            response = await agent.client.generate(
                adapter.format_messages(history),
                **gen_kwargs,
            )
            parsed = adapter.parse(response)

            # Check for handoff
            for tc in parsed.tool_calls:
                if tc.name.startswith(_HANDOFF_PREFIX):
                    target_name = tc.name[
                        len(_HANDOFF_PREFIX):
                    ]
                    # Callback: handoff
                    if self._callbacks:
                        for cb in self._callbacks:
                            if hasattr(cb, 'on_handoff'):
                                await cb.on_handoff(
                                    agent.name,
                                    target_name,
                                )
                    # Append assistant message to history
                    history.append(
                        adapter.format_assistant_message(
                            response
                        )
                    )
                    return AgentResult(
                        agent_name=agent.name,
                        text=parsed.text,
                        history=history,
                        handoff_to=target_name,
                    )

            # No tool calls — final response
            if not parsed.tool_calls:
                history.append(
                    adapter.format_assistant_message(
                        response
                    )
                )
                # Callback: iteration end
                if self._callbacks:
                    for cb in self._callbacks:
                        if hasattr(cb, 'on_iteration_end'):
                            await cb.on_iteration_end(
                                agent.name, _iteration,
                            )
                return AgentResult(
                    agent_name=agent.name,
                    text=parsed.text,
                    history=history,
                )

            # Execute tool calls
            history.append(
                adapter.format_assistant_message(response)
            )

            calls = [
                (tc.name, tc.id, tc.arguments)
                for tc in parsed.tool_calls
            ]

            # Callback: tool start (per tool)
            if self._callbacks:
                for tc in parsed.tool_calls:
                    for cb in self._callbacks:
                        if hasattr(cb, 'on_tool_start'):
                            await cb.on_tool_start(
                                agent.name,
                                tc.name,
                                tc.arguments,
                            )

            results = await registry.execute_many(calls)

            # Callback: tool end (per tool)
            if self._callbacks:
                for r in results:
                    for cb in self._callbacks:
                        if hasattr(cb, 'on_tool_end'):
                            await cb.on_tool_end(
                                agent.name,
                                r.name,
                                {},
                                r.output,
                                r.error,
                                r.success,
                            )

            result_dicts = [
                {
                    'call_id': r.call_id,
                    'name': r.name,
                    'success': r.success,
                    'output': r.output,
                    'error': r.error,
                }
                for r in results
            ]

            tool_msg = adapter.format_tool_results_message(
                result_dicts
            )
            if isinstance(tool_msg, list):
                history.extend(tool_msg)
            else:
                history.append(tool_msg)

            # Callback: iteration end
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_iteration_end'):
                        await cb.on_iteration_end(
                            agent.name, _iteration,
                        )

        raise AgentError(
            agent.name,
            f'Exceeded max_iterations '
            f'({agent.max_iterations})',
        )
