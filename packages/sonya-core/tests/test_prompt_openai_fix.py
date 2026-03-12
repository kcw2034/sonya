"""Tests for OpenAI system message injection fix."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.parsers.adapter import OpenAIAdapter
from sonya.core.models.agent import Agent
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.client.base import BaseClient
from sonya.core.schemas.types import ClientConfig


# --- Adapter tests ---

def test_openai_format_generate_kwargs_includes_system():
    adapter = OpenAIAdapter()
    kwargs = adapter.format_generate_kwargs(
        'You are helpful.', None
    )
    assert '_system_message' in kwargs
    assert kwargs['_system_message'] == 'You are helpful.'


def test_openai_format_generate_kwargs_no_instructions():
    adapter = OpenAIAdapter()
    kwargs = adapter.format_generate_kwargs('', None)
    assert '_system_message' not in kwargs


def test_openai_format_generate_kwargs_with_tools():
    adapter = OpenAIAdapter()
    tools = [{'type': 'function', 'function': {'name': 'f'}}]
    kwargs = adapter.format_generate_kwargs(
        'Be helpful.', tools
    )
    assert kwargs['_system_message'] == 'Be helpful.'
    assert kwargs['tools'] == tools


# --- Runtime integration tests ---

class _DummyOpenAIClient(BaseClient):
    """Fake OpenAI client that captures messages."""

    def __init__(self) -> None:
        super().__init__(ClientConfig(model='test'))
        self.captured_messages: list[dict[str, Any]] | None = None

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        self.captured_messages = messages
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='ok',
                        tool_calls=None,
                    ),
                    finish_reason='stop',
                )
            ]
        )

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(
            messages, **kwargs
        )


_DummyOpenAIClient.__name__ = 'OpenAIClient'


@pytest.mark.asyncio
async def test_runtime_prepends_system_message_for_openai():
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='You are helpful.',
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'system'
    assert msgs[0]['content'] == 'You are helpful.'
    assert msgs[1]['role'] == 'user'


@pytest.mark.asyncio
async def test_runtime_no_system_message_when_empty():
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='',
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'user'


@pytest.mark.asyncio
async def test_runtime_no_duplicate_system_when_history_has_system():
    """When history already contains a system message and agent has
    instructions, only the agent's instructions should appear as the
    system message — not both."""
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='You are helpful.',
    )
    runtime = AgentRuntime(agent)
    await runtime.run([
        {'role': 'system', 'content': 'Caller system prompt.'},
        {'role': 'user', 'content': 'hi'},
    ])
    msgs = client.captured_messages
    system_msgs = [
        m for m in msgs if m.get('role') == 'system'
    ]
    assert len(system_msgs) == 1, (
        f'Expected 1 system message, got {len(system_msgs)}: '
        f'{system_msgs}'
    )
    assert system_msgs[0]['content'] == 'You are helpful.'


@pytest.mark.asyncio
async def test_runtime_preserves_system_when_no_instructions():
    """When agent has no instructions, any existing system message
    in history must be preserved unchanged."""
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='',
    )
    runtime = AgentRuntime(agent)
    await runtime.run([
        {'role': 'system', 'content': 'Caller system prompt.'},
        {'role': 'user', 'content': 'hi'},
    ])
    msgs = client.captured_messages
    system_msgs = [
        m for m in msgs if m.get('role') == 'system'
    ]
    assert len(system_msgs) == 1
    assert system_msgs[0]['content'] == 'Caller system prompt.'


@pytest.mark.asyncio
async def test_runtime_agent_instructions_first_in_messages():
    """After dedup, agent instructions must be at index 0."""
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='Agent instructions.',
    )
    runtime = AgentRuntime(agent)
    await runtime.run([
        {'role': 'system', 'content': 'Old system.'},
        {'role': 'user', 'content': 'hello'},
    ])
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'system'
    assert msgs[0]['content'] == 'Agent instructions.'
    assert msgs[1]['role'] == 'user'
