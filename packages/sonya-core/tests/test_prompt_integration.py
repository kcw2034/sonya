"""Integration tests for the Prompt system."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core import Agent, AgentRuntime, Prompt, Example
from sonya.core.client.provider.base import BaseClient
from sonya.core.schemas.types import ClientConfig


class _DummyAnthropicClient(BaseClient):
    """Fake Anthropic client that captures kwargs."""

    def __init__(self) -> None:
        super().__init__(ClientConfig(model='test'))
        self.captured_kwargs: dict[str, Any] | None = None

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        self.captured_kwargs = kwargs
        return SimpleNamespace(
            content=[
                SimpleNamespace(type='text', text='ok')
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


_DummyAnthropicClient.__name__ = 'AnthropicClient'


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
async def test_structured_prompt_with_anthropic() -> None:
    """Prompt renders and passes to Anthropic as system."""
    client = _DummyAnthropicClient()
    agent = Agent(
        name='test',
        client=client,
        instructions=Prompt(
            role='You are a weather bot.',
            guidelines=('Be concise.',),
            constraints=('No fabrication.',),
            examples=(
                Example(
                    user='Weather in Seoul?',
                    assistant='Checking...',
                ),
            ),
        ),
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    system = client.captured_kwargs.get('system', '')
    assert 'You are a weather bot.' in system
    assert '## Guidelines' in system
    assert '- Be concise.' in system
    assert '## Constraints' in system
    assert 'User: Weather in Seoul?' in system


@pytest.mark.asyncio
async def test_dynamic_prompt_with_openai() -> None:
    """Dynamic Prompt renders with context for OpenAI."""
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions=Prompt(
            role='You are a {domain} expert.',
        ),
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}],
        prompt_context={'domain': 'cooking'},
    )
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'system'
    assert 'cooking expert' in msgs[0]['content']


@pytest.mark.asyncio
async def test_backward_compat_str_instructions() -> None:
    """Plain string instructions still work."""
    client = _DummyAnthropicClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='Be helpful.',
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert client.captured_kwargs['system'] == 'Be helpful.'
