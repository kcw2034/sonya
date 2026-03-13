"""AgentRuntime — the LLM <-> tool execution loop."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, cast

from sonya.core.parsers.adapter import get_adapter
from sonya.core.exceptions.errors import AgentError, GuardrailError
from sonya.core.schemas.types import UsageSummary
from sonya.core.client.provider.interceptor import extract_usage
from sonya.core.utils.validation import validate_input
from sonya.core.utils.tool_context import ToolContext
from sonya.core.utils.handoff import _HANDOFF_PREFIX

from .agent import AgentResult

if TYPE_CHECKING:
    from .agent import Agent
from .tool import ToolResult
from .tool_registry import ToolRegistry
from .prompt import Prompt

# Maps provider client class names to schema format names.
# Defined at module level to avoid recreation on every run().
_PROVIDER_MAP: dict[str, str] = {
    'AnthropicClient': 'anthropic',
    'OpenAIClient': 'openai',
    'GeminiClient': 'gemini',
}


def _try_parse_json(
    text: str,
) -> dict[str, Any] | None:
    """Attempt to parse *text* as a JSON object.

    Returns the parsed dict on success, or None if parsing fails
    or the result is not a dict.
    """
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


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
        self._adapter = get_adapter(agent.client)
        self._registry = self._build_registry()
        self._callbacks = agent.callbacks
        # Link the registry to the context so tools can call
        # ctx.add_tool() / ctx.remove_tool() during execution.
        if context is not None:
            context._registry = self._registry
            self._context = context
        else:
            self._context = ToolContext(registry=self._registry)

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

    async def _check_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Check if a tool requiring approval is allowed to run.

        Calls ``on_approval_request`` on all registered callbacks.
        Returns False if any callback denies; True otherwise.
        If no callback implements ``on_approval_request``, defaults
        to True (approve silently).

        Args:
            tool_name: Name of the tool requesting approval.
            arguments: Arguments passed to the tool.

        Returns:
            True if approved, False if denied.
        """
        if not self._callbacks:
            return True
        for cb in self._callbacks:
            if not hasattr(cb, 'on_approval_request'):
                continue
            approved = await cb.on_approval_request(
                self._agent.name,
                tool_name,
                arguments,
            )
            if not approved:
                return False
        return True

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
        instructions = agent.instructions
        if isinstance(instructions, Prompt):
            instructions = instructions.render(
                **(prompt_context or {})
            )

        # Determine provider format once (class name is stable).
        provider_name = type(agent.client).__name__
        _provider = _PROVIDER_MAP.get(provider_name, 'openai')

        # Inject system message into history once before the loop.
        # Use initial schemas for the first format_generate_kwargs
        # call solely to extract the system message.
        _init_schemas: list[dict[str, Any]] | None = None
        if registry.tools:
            _init_schemas = registry.schemas(_provider)
        _init_kwargs = adapter.format_generate_kwargs(
            instructions,
            _init_schemas,
            output_schema=agent.output_schema,
        )
        # Extract system message for OpenAI-style injection.
        # Strip any pre-existing system messages from history to
        # ensure the agent's instructions are the sole system
        # message and avoid duplicates when history is passed
        # from a previous agent (e.g. via Runner handoff).
        system_message = _init_kwargs.pop(
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

        guardrails = agent.guardrails
        _total_tool_calls = 0
        _total_tool_time = 0.0
        # Observability counters
        _total_input_tokens = 0
        _total_output_tokens = 0
        _llm_calls = 0
        _total_latency_ms = 0.0

        for _iteration in range(agent.max_iterations):
            # Regenerate schemas from live registry so any tools
            # added or removed since the last iteration are reflected.
            _current_schemas: list[dict[str, Any]] | None = None
            if registry.tools:
                _current_schemas = registry.schemas(_provider)
            gen_kwargs = adapter.format_generate_kwargs(
                instructions,
                _current_schemas,
                output_schema=agent.output_schema,
            )
            # System message is already in history; discard the key.
            gen_kwargs.pop('_system_message', None)

            # Callback: iteration start
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_iteration_start'):
                        await cb.on_iteration_start(
                            agent.name, _iteration,
                        )

            _formatted_msgs = adapter.format_messages(history)
            # Callback: LLM call start
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_llm_start'):
                        await cb.on_llm_start(
                            agent.name,
                            _iteration,
                            len(_formatted_msgs),
                        )

            _t_llm_start = time.monotonic()
            response = await agent.client.generate(
                _formatted_msgs,
                **gen_kwargs,
            )
            _iter_latency_ms = (
                time.monotonic() - _t_llm_start
            ) * 1000
            _total_latency_ms += _iter_latency_ms
            _llm_calls += 1
            _inp, _out = extract_usage(response)
            _total_input_tokens += _inp
            _total_output_tokens += _out
            parsed = adapter.parse(response)

            # Callback: LLM call end
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_llm_end'):
                        await cb.on_llm_end(
                            agent.name,
                            _iteration,
                            _inp,
                            _out,
                            _iter_latency_ms,
                        )

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
                        metadata={
                            'usage': UsageSummary(
                                total_input_tokens=_total_input_tokens,
                                total_output_tokens=_total_output_tokens,
                                llm_calls=_llm_calls,
                                iterations=_iteration + 1,
                                total_tool_calls=_total_tool_calls,
                                total_tool_time_ms=_total_tool_time * 1000,
                                total_latency_ms=_total_latency_ms,
                            )
                        },
                    )

            # No tool calls — final response
            if not parsed.tool_calls:
                # Structured output: parse + validate JSON
                if agent.output_schema is not None:
                    parsed_out = _try_parse_json(parsed.text)
                    if parsed_out is None:
                        # Not valid JSON — ask model to fix
                        history.append(
                            adapter.format_assistant_message(
                                response
                            )
                        )
                        history.append({
                            'role': 'user',
                            'content': (
                                'Your response must be valid '
                                'JSON matching the required '
                                'schema. Please try again.'
                            ),
                        })
                        continue
                    errors = validate_input(
                        parsed_out, agent.output_schema
                    )
                    if errors:
                        history.append(
                            adapter.format_assistant_message(
                                response
                            )
                        )
                        history.append({
                            'role': 'user',
                            'content': (
                                f'JSON validation errors: '
                                f'{errors}. '
                                f'Fix and respond again.'
                            ),
                        })
                        continue
                    history.append(
                        adapter.format_assistant_message(
                            response
                        )
                    )
                    if self._callbacks:
                        for cb in self._callbacks:
                            if hasattr(
                                cb, 'on_iteration_end'
                            ):
                                await cb.on_iteration_end(
                                    agent.name,
                                    _iteration,
                                )
                    return AgentResult(
                        agent_name=agent.name,
                        text=parsed.text,
                        history=history,
                        output=parsed_out,
                        metadata={
                            'usage': UsageSummary(
                                total_input_tokens=_total_input_tokens,
                                total_output_tokens=_total_output_tokens,
                                llm_calls=_llm_calls,
                                iterations=_iteration + 1,
                                total_tool_calls=_total_tool_calls,
                                total_tool_time_ms=_total_tool_time * 1000,
                                total_latency_ms=_total_latency_ms,
                            )
                        },
                    )

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
                    metadata={
                        'usage': UsageSummary(
                            total_input_tokens=_total_input_tokens,
                            total_output_tokens=_total_output_tokens,
                            llm_calls=_llm_calls,
                            iterations=_iteration + 1,
                            total_tool_calls=_total_tool_calls,
                            total_tool_time_ms=_total_tool_time * 1000,
                            total_latency_ms=_total_latency_ms,
                        )
                    },
                )

            # Execute tool calls
            history.append(
                adapter.format_assistant_message(response)
            )

            calls = [
                (tc.name, tc.id, tc.arguments)
                for tc in parsed.tool_calls
            ]

            # Guardrail: tool call count
            _total_tool_calls += len(calls)
            if (
                guardrails.max_tool_calls is not None
                and _total_tool_calls
                > guardrails.max_tool_calls
            ):
                raise GuardrailError(
                    agent.name,
                    f'tool call limit exceeded: '
                    f'{_total_tool_calls}'
                    f'/{guardrails.max_tool_calls}',
                )

            # Approval check: separate approved from denied calls
            approved_calls: list[
                tuple[str, str, dict[str, Any] | str]
            ] = []
            denied_results: list[ToolResult] = []
            for tc in parsed.tool_calls:
                t_obj = registry.get(tc.name)
                if (
                    t_obj is not None
                    and t_obj.requires_approval
                    and not await self._check_approval(
                        tc.name, tc.arguments
                    )
                ):
                    denied_results.append(ToolResult(
                        call_id=tc.id,
                        name=tc.name,
                        success=False,
                        error=(
                            f"Tool '{tc.name}' execution "
                            f'denied by user approval'
                        ),
                    ))
                else:
                    approved_calls.append(
                        (tc.name, tc.id, tc.arguments)
                    )

            # Callback: tool start (per approved tool)
            if self._callbacks:
                for name_, _, args_ in approved_calls:
                    for cb in self._callbacks:
                        if hasattr(cb, 'on_tool_start'):
                            await cb.on_tool_start(
                                agent.name,
                                name_,
                                cast(
                                    dict[str, Any], args_
                                ),
                            )

            _t0 = time.monotonic()
            if approved_calls:
                if not agent.parallel_tool_execution:
                    executed = await registry.execute_sequential(
                        approved_calls,
                        context=self._context,
                    )
                elif guardrails.max_concurrent_tools is not None:
                    executed = await registry.execute_many(
                        approved_calls,
                        max_concurrency=guardrails.max_concurrent_tools,
                        context=self._context,
                    )
                else:
                    executed = await registry.execute_many(
                        approved_calls,
                        context=self._context,
                    )
            else:
                executed = []
            _total_tool_time += time.monotonic() - _t0
            results = denied_results + executed

            # Guardrail: cumulative tool time
            if (
                guardrails.max_tool_time is not None
                and _total_tool_time
                > guardrails.max_tool_time
            ):
                raise GuardrailError(
                    agent.name,
                    f'tool time limit exceeded: '
                    f'{_total_tool_time:.2f}s'
                    f'/{guardrails.max_tool_time}s',
                )

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

    async def run_stream(
        self,
        messages: list[dict[str, Any]],
        prompt_context: dict[str, str] | None = None,
    ) -> AsyncGenerator[str | AgentResult, None]:
        """Execute the agent loop, streaming text and result.

        Yields text from each LLM iteration as it becomes
        available, then yields the final :class:`AgentResult`
        as the last item.

        This enables progressive display of agent output
        across multi-iteration loops (e.g., tool-calling
        agents) without waiting for the full loop to finish.

        Args:
            messages: Initial conversation messages.
            prompt_context: Template variables for
                :meth:`Prompt.render` when *instructions*
                is a :class:`Prompt`.

        Yields:
            str: Text from each LLM response (non-empty only).
            AgentResult: Final result as the last yielded item.

        Raises:
            AgentError: If the loop exceeds max_iterations.
        """
        agent = self._agent
        adapter = self._adapter
        registry = self._registry
        history = list(messages)

        instructions = agent.instructions
        if isinstance(instructions, Prompt):
            instructions = instructions.render(
                **(prompt_context or {})
            )

        _s_provider_name = type(agent.client).__name__
        _s_provider = _PROVIDER_MAP.get(
            _s_provider_name, 'openai'
        )

        # Inject system message into history once before the loop.
        _s_init_schemas: list[dict[str, Any]] | None = None
        if registry.tools:
            _s_init_schemas = registry.schemas(_s_provider)
        _s_init_kwargs = adapter.format_generate_kwargs(
            instructions,
            _s_init_schemas,
            output_schema=agent.output_schema,
        )
        system_message = _s_init_kwargs.pop(
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

        _stream_total_tool_calls = 0
        _stream_total_tool_time = 0.0
        _stream_guardrails = agent.guardrails
        # Observability counters
        _s_total_input_tokens = 0
        _s_total_output_tokens = 0
        _s_llm_calls = 0
        _s_total_latency_ms = 0.0

        for _iteration in range(agent.max_iterations):
            # Regenerate schemas from live registry each iteration.
            _s_current_schemas: list[dict[str, Any]] | None = None
            if registry.tools:
                _s_current_schemas = registry.schemas(_s_provider)
            gen_kwargs = adapter.format_generate_kwargs(
                instructions,
                _s_current_schemas,
                output_schema=agent.output_schema,
            )
            gen_kwargs.pop('_system_message', None)

            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_iteration_start'):
                        await cb.on_iteration_start(
                            agent.name, _iteration,
                        )

            _s_formatted_msgs = adapter.format_messages(history)
            # Callback: LLM call start
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_llm_start'):
                        await cb.on_llm_start(
                            agent.name,
                            _iteration,
                            len(_s_formatted_msgs),
                        )

            _st_llm = time.monotonic()
            response = await agent.client.generate(
                _s_formatted_msgs,
                **gen_kwargs,
            )
            _s_iter_latency_ms = (
                time.monotonic() - _st_llm
            ) * 1000
            _s_total_latency_ms += _s_iter_latency_ms
            _s_llm_calls += 1
            _s_inp, _s_out = extract_usage(response)
            _s_total_input_tokens += _s_inp
            _s_total_output_tokens += _s_out
            parsed = adapter.parse(response)

            # Callback: LLM call end
            if self._callbacks:
                for cb in self._callbacks:
                    if hasattr(cb, 'on_llm_end'):
                        await cb.on_llm_end(
                            agent.name,
                            _iteration,
                            _s_inp,
                            _s_out,
                            _s_iter_latency_ms,
                        )

            # Yield text chunk if present
            if parsed.text:
                yield parsed.text

            # Check for handoff
            for tc in parsed.tool_calls:
                if tc.name.startswith(_HANDOFF_PREFIX):
                    target_name = tc.name[
                        len(_HANDOFF_PREFIX):
                    ]
                    if self._callbacks:
                        for cb in self._callbacks:
                            if hasattr(cb, 'on_handoff'):
                                await cb.on_handoff(
                                    agent.name,
                                    target_name,
                                )
                    history.append(
                        adapter.format_assistant_message(
                            response
                        )
                    )
                    yield AgentResult(
                        agent_name=agent.name,
                        text=parsed.text,
                        history=history,
                        handoff_to=target_name,
                        metadata={
                            'usage': UsageSummary(
                                total_input_tokens=_s_total_input_tokens,
                                total_output_tokens=_s_total_output_tokens,
                                llm_calls=_s_llm_calls,
                                iterations=_iteration + 1,
                                total_tool_calls=_stream_total_tool_calls,
                                total_tool_time_ms=_stream_total_tool_time * 1000,
                                total_latency_ms=_s_total_latency_ms,
                            )
                        },
                    )
                    return

            # No tool calls — final response
            if not parsed.tool_calls:
                # Structured output: parse + validate JSON
                if agent.output_schema is not None:
                    parsed_out = _try_parse_json(parsed.text)
                    if parsed_out is None:
                        history.append(
                            adapter.format_assistant_message(
                                response
                            )
                        )
                        history.append({
                            'role': 'user',
                            'content': (
                                'Your response must be valid '
                                'JSON matching the required '
                                'schema. Please try again.'
                            ),
                        })
                        continue
                    errors = validate_input(
                        parsed_out, agent.output_schema
                    )
                    if errors:
                        history.append(
                            adapter.format_assistant_message(
                                response
                            )
                        )
                        history.append({
                            'role': 'user',
                            'content': (
                                f'JSON validation errors: '
                                f'{errors}. '
                                f'Fix and respond again.'
                            ),
                        })
                        continue
                    history.append(
                        adapter.format_assistant_message(
                            response
                        )
                    )
                    if self._callbacks:
                        for cb in self._callbacks:
                            if hasattr(
                                cb, 'on_iteration_end'
                            ):
                                await cb.on_iteration_end(
                                    agent.name,
                                    _iteration,
                                )
                    yield AgentResult(
                        agent_name=agent.name,
                        text=parsed.text,
                        history=history,
                        output=parsed_out,
                        metadata={
                            'usage': UsageSummary(
                                total_input_tokens=_s_total_input_tokens,
                                total_output_tokens=_s_total_output_tokens,
                                llm_calls=_s_llm_calls,
                                iterations=_iteration + 1,
                                total_tool_calls=_stream_total_tool_calls,
                                total_tool_time_ms=_stream_total_tool_time * 1000,
                                total_latency_ms=_s_total_latency_ms,
                            )
                        },
                    )
                    return

                history.append(
                    adapter.format_assistant_message(
                        response
                    )
                )
                if self._callbacks:
                    for cb in self._callbacks:
                        if hasattr(cb, 'on_iteration_end'):
                            await cb.on_iteration_end(
                                agent.name, _iteration,
                            )
                yield AgentResult(
                    agent_name=agent.name,
                    text=parsed.text,
                    history=history,
                    metadata={
                        'usage': UsageSummary(
                            total_input_tokens=_s_total_input_tokens,
                            total_output_tokens=_s_total_output_tokens,
                            llm_calls=_s_llm_calls,
                            iterations=_iteration + 1,
                            total_tool_calls=_stream_total_tool_calls,
                            total_tool_time_ms=_stream_total_tool_time * 1000,
                            total_latency_ms=_s_total_latency_ms,
                        )
                    },
                )
                return

            # Execute tool calls
            history.append(
                adapter.format_assistant_message(response)
            )
            calls = [
                (tc.name, tc.id, tc.arguments)
                for tc in parsed.tool_calls
            ]

            # Guardrail: tool call count
            _stream_total_tool_calls += len(calls)
            if (
                _stream_guardrails.max_tool_calls is not None
                and _stream_total_tool_calls
                > _stream_guardrails.max_tool_calls
            ):
                raise GuardrailError(
                    agent.name,
                    f'tool call limit exceeded: '
                    f'{_stream_total_tool_calls}'
                    f'/{_stream_guardrails.max_tool_calls}',
                )

            # Approval check: separate approved from denied calls
            _s_approved: list[
                tuple[str, str, dict[str, Any] | str]
            ] = []
            _s_denied: list[ToolResult] = []
            for tc in parsed.tool_calls:
                t_obj = registry.get(tc.name)
                if (
                    t_obj is not None
                    and t_obj.requires_approval
                    and not await self._check_approval(
                        tc.name, tc.arguments
                    )
                ):
                    _s_denied.append(ToolResult(
                        call_id=tc.id,
                        name=tc.name,
                        success=False,
                        error=(
                            f"Tool '{tc.name}' execution "
                            f'denied by user approval'
                        ),
                    ))
                else:
                    _s_approved.append(
                        (tc.name, tc.id, tc.arguments)
                    )

            if self._callbacks:
                for name_, _, args_ in _s_approved:
                    for cb in self._callbacks:
                        if hasattr(cb, 'on_tool_start'):
                            await cb.on_tool_start(
                                agent.name,
                                name_,
                                cast(
                                    dict[str, Any], args_
                                ),
                            )

            _st0 = time.monotonic()
            if _s_approved:
                _stream_guardrails = agent.guardrails
                if not agent.parallel_tool_execution:
                    _s_executed = await registry.execute_sequential(
                        _s_approved,
                        context=self._context,
                    )
                elif _stream_guardrails.max_concurrent_tools is not None:
                    _s_executed = await registry.execute_many(
                        _s_approved,
                        max_concurrency=_stream_guardrails.max_concurrent_tools,
                        context=self._context,
                    )
                else:
                    _s_executed = await registry.execute_many(
                        _s_approved,
                        context=self._context,
                    )
            else:
                _s_executed = []
            _stream_total_tool_time += (
                time.monotonic() - _st0
            )
            results = _s_denied + _s_executed

            # Guardrail: cumulative tool time
            if (
                _stream_guardrails.max_tool_time is not None
                and _stream_total_tool_time
                > _stream_guardrails.max_tool_time
            ):
                raise GuardrailError(
                    agent.name,
                    f'tool time limit exceeded: '
                    f'{_stream_total_tool_time:.2f}s'
                    f'/{_stream_guardrails.max_tool_time}s',
                )

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
