"""Tests for ToolContext dynamic tool registration interface."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent import Agent
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.tool import Tool
from sonya.core.models.tool_registry import ToolRegistry
from sonya.core.utils.tool_context import ToolContext
from sonya.core.utils.decorator import tool
from sonya.core.client.provider.base import BaseClient
from sonya.core.schemas.types import ClientConfig


# --- ToolContext registry interface ---

def _make_tool(name: str) -> Tool:
    async def fn() -> str:
        return name

    return Tool(
        name=name,
        description='test tool',
        fn=fn,
        schema={'type': 'object', 'properties': {}},
    )


def test_tool_context_add_tool_registers_in_registry() -> None:
    registry = ToolRegistry()
    ctx = ToolContext(registry=registry)
    ctx.add_tool(_make_tool('dynamic'))
    assert registry.has('dynamic')


def test_tool_context_remove_tool_unregisters_from_registry() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('existing'))
    ctx = ToolContext(registry=registry)
    ctx.remove_tool('existing')
    assert not registry.has('existing')


def test_tool_context_add_tool_without_registry_raises() -> None:
    ctx = ToolContext()
    with pytest.raises(RuntimeError, match='registry'):
        ctx.add_tool(_make_tool('orphan'))


def test_tool_context_remove_tool_without_registry_raises() -> None:
    ctx = ToolContext()
    with pytest.raises(RuntimeError, match='registry'):
        ctx.remove_tool('orphan')


def test_tool_context_kv_store_unaffected_by_registry() -> None:
    """Existing KV store API must still work when a registry is bound."""
    registry = ToolRegistry()
    ctx = ToolContext(registry=registry)
    ctx.set('key', 'value')
    assert ctx.get('key') == 'value'
    assert ctx.has('key') is True


# --- AgentRuntime links registry to ToolContext ---

class _DummyClient(BaseClient):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._call_count = 0
        self.captured_kwargs: list[dict[str, Any]] = []

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        self.captured_kwargs.append(dict(kwargs))
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _anthropic_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _anthropic_tool_call(
    tool_name: str,
    tool_id: str,
    tool_input: dict[str, Any],
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type='tool_use',
                id=tool_id,
                name=tool_name,
                input=tool_input,
            )
        ],
        stop_reason='tool_use',
    )


@pytest.mark.asyncio
async def test_agent_runtime_links_registry_to_context() -> None:
    """AgentRuntime should bind its registry to the provided ToolContext."""
    ctx = ToolContext()
    client = _DummyClient([_anthropic_text('done')])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='test_agent',
        instructions='be helpful',
        client=client,
    )
    runtime = AgentRuntime(agent, context=ctx)

    # After construction, ctx should be linked to registry
    assert ctx._registry is runtime._registry


@pytest.mark.asyncio
async def test_dynamic_tool_registered_during_run_appears_in_next_iteration() -> None:
    """A tool registered via ToolContext during iteration N is visible in N+1."""
    ctx = ToolContext()

    # We'll capture which tool schemas are passed to the LLM each call
    generate_kwargs_log: list[dict[str, Any]] = []

    class _CapturingClient(BaseClient):
        def __init__(self, responses: list[Any]) -> None:
            super().__init__(ClientConfig(model='dummy'))
            self._responses = list(responses)
            self._call_count = 0

        async def _provider_generate(
            self, messages: list[dict[str, Any]], **kwargs: Any
        ) -> Any:
            generate_kwargs_log.append(dict(kwargs))
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp

        async def _provider_generate_stream(
            self, messages: list[dict[str, Any]], **kwargs: Any
        ) -> AsyncIterator[Any]:
            yield await self._provider_generate(messages, **kwargs)

    # tool_a registers tool_b when executed
    @tool()
    async def tool_a() -> str:
        """Registers tool_b dynamically."""
        @tool()
        async def tool_b() -> str:
            """Dynamically registered tool."""
            return 'tool_b result'

        ctx.add_tool(tool_b)
        return 'tool_a done'

    _client = _CapturingClient([
        # First LLM call: request tool_a
        _anthropic_tool_call('tool_a', 'c1', {}),
        # Second LLM call: final text (after tool_b is visible)
        _anthropic_text('finished'),
    ])
    _client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='dyn_agent',
        instructions='test',
        client=_client,
        tools=[tool_a],
    )
    runtime = AgentRuntime(agent, context=ctx)
    await runtime.run([{'role': 'user', 'content': 'go'}])

    # Second generate() call should include tool_b in schemas
    assert len(generate_kwargs_log) == 2
    second_call_tools = generate_kwargs_log[1].get('tools', [])
    tool_names_second = [t['name'] for t in second_call_tools]
    assert 'tool_b' in tool_names_second
    # First call should NOT have tool_b
    first_call_tools = generate_kwargs_log[0].get('tools', [])
    tool_names_first = [t['name'] for t in first_call_tools]
    assert 'tool_b' not in tool_names_first
