"""Tests for AgentRuntime Prompt integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent import Agent, AgentResult
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.prompt import Prompt, Example
from sonya.core.client.provider.base import BaseClient
from sonya.core.schemas.types import ClientConfig


class _DummyClient(BaseClient):
    """Client that returns a canned text response."""

    def __init__(self, text: str = 'hello') -> None:
        super().__init__(ClientConfig(model='test'))
        self._text = text

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        return SimpleNamespace(
            content=[
                SimpleNamespace(type='text', text=self._text)
            ],
            stop_reason='end_turn',
        )

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(
            messages, **kwargs
        )


def _make_client(text: str = 'hello') -> _DummyClient:
    """Create a _DummyClient with AnthropicClient adapter."""
    client = _DummyClient(text)
    client.__class__.__name__ = 'AnthropicClient'
    return client


@pytest.mark.asyncio
async def test_runtime_with_str_instructions() -> None:
    """Runtime works with plain string instructions."""
    agent = Agent(
        name='test',
        client=_make_client(),
        instructions='Be helpful.',
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'hello'


@pytest.mark.asyncio
async def test_runtime_with_prompt_instructions() -> None:
    """Runtime works with Prompt object as instructions."""
    agent = Agent(
        name='test',
        client=_make_client(),
        instructions=Prompt(
            role='You are a bot.',
            guidelines=('Be concise.',),
        ),
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'hello'


@pytest.mark.asyncio
async def test_runtime_with_prompt_context() -> None:
    """Runtime renders Prompt templates via prompt_context."""
    agent = Agent(
        name='test',
        client=_make_client(),
        instructions=Prompt(
            role='You are a {domain} expert.',
        ),
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}],
        prompt_context={'domain': 'weather'},
    )
    assert result.text == 'hello'


@pytest.mark.asyncio
async def test_runtime_prompt_context_ignored_for_str() -> None:
    """prompt_context is safely ignored for string instructions."""
    agent = Agent(
        name='test',
        client=_make_client(),
        instructions='Static prompt.',
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}],
        prompt_context={'domain': 'weather'},
    )
    assert result.text == 'hello'
