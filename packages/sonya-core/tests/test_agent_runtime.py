"""Tests for AgentRuntime with a DummyClient."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.agent.runtime import AgentRuntime
from sonya.core.agent.types import Agent
from sonya.core.client.base import BaseClient
from sonya.core.errors import AgentError
from sonya.core.tool.decorator import tool
from sonya.core.types import ClientConfig


class DummyClient(BaseClient):
    """A mock client that returns pre-configured responses."""

    def __init__(
        self, responses: list[Any], model: str = 'dummy'
    ) -> None:
        super().__init__(ClientConfig(model=model))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        if self._call_count >= len(self._responses):
            raise RuntimeError('No more mock responses')
        response = self._responses[self._call_count]
        self._call_count += 1
        return response

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _make_anthropic_text_response(text: str) -> SimpleNamespace:
    """Create a mock Anthropic text-only response."""
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _make_anthropic_tool_response(
    text: str,
    tool_name: str,
    tool_id: str,
    tool_input: dict[str, Any],
) -> SimpleNamespace:
    """Create a mock Anthropic response with a tool call."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(type='text', text=text),
            SimpleNamespace(
                type='tool_use',
                id=tool_id,
                name=tool_name,
                input=tool_input,
            ),
        ],
        stop_reason='tool_use',
    )


@pytest.mark.asyncio
async def test_simple_text_response() -> None:
    client = DummyClient(
        [_make_anthropic_text_response('Hello!')]
    )
    # Patch class name so adapter is detected
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(name='test_agent', client=client)
    runtime = AgentRuntime(agent)
    result = await runtime.run([
        {'role': 'user', 'content': 'Hi'}
    ])

    assert result.agent_name == 'test_agent'
    assert result.text == 'Hello!'
    assert result.handoff_to is None


@pytest.mark.asyncio
async def test_tool_use_loop() -> None:
    @tool(description='Add two numbers')
    def add(a: int, b: int) -> int:
        return a + b

    client = DummyClient([
        _make_anthropic_tool_response(
            'Let me add', 'add', 'tc_1', {'a': 3, 'b': 4}
        ),
        _make_anthropic_text_response('The result is 7'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='calc_agent',
        client=client,
        tools=[add],
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run([
        {'role': 'user', 'content': 'What is 3 + 4?'}
    ])

    assert result.text == 'The result is 7'
    assert len(result.history) > 1


@pytest.mark.asyncio
async def test_max_iterations_exceeded() -> None:
    """Agent should raise AgentError when max_iterations is hit."""

    @tool(description='Always called')
    def noop() -> str:
        return 'ok'

    # Always return a tool call — never stops
    responses = [
        _make_anthropic_tool_response(
            '', 'noop', f'tc_{i}', {}
        )
        for i in range(5)
    ]
    client = DummyClient(responses)
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='loop_agent',
        client=client,
        tools=[noop],
        max_iterations=3,
    )
    runtime = AgentRuntime(agent)

    with pytest.raises(AgentError, match='max_iterations'):
        await runtime.run([
            {'role': 'user', 'content': 'Go'}
        ])
