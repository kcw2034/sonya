"""Tests for ContextRouter."""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent import Agent
from sonya.core.client.base import BaseClient
from sonya.core.schemas.memory import (
    NormalizedMessage,
)
from sonya.core.utils.router import ContextRouter
from sonya.core.utils.tool_context import ToolContext
from sonya.core.schemas.types import ClientConfig


# --- Helpers ---

class _DummyClient(BaseClient):
    """Minimal client for testing provider detection."""

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        return {}

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield {}


def _make_agent(
    name: str, client: BaseClient,
) -> Agent:
    return Agent(name=name, client=client)


def _client(provider_name: str) -> _DummyClient:
    # Create a unique subclass so __name__ is isolated
    cls = type(provider_name, (_DummyClient,), {})
    return cls(ClientConfig(model='test'))


# --- Fake pipelines ---

class _FakePipeline:
    """Pipeline that uppercases content on reconstruct."""

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        return [
            NormalizedMessage(
                role=m.get('role', 'user'),
                content=m.get('content', ''),
                metadata={'source': source_provider},
            )
            for m in history
        ]

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                'role': m.role,
                'content': m.content.upper(),
            }
            for m in messages
        ]


class _FailingPipeline:
    """Pipeline that always raises on normalize."""

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        raise RuntimeError('normalize failed')

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        return []


# --- Provider detection tests ---

class TestProviderDetection:
    """Verify _detect_provider works for all known clients."""

    def test_anthropic(self) -> None:
        agent = _make_agent('a', _client('AnthropicClient'))
        router = ContextRouter()
        assert router._detect_provider(agent) == 'anthropic'

    def test_openai(self) -> None:
        agent = _make_agent('a', _client('OpenAIClient'))
        router = ContextRouter()
        assert router._detect_provider(agent) == 'openai'

    def test_gemini(self) -> None:
        agent = _make_agent('a', _client('GeminiClient'))
        router = ContextRouter()
        assert router._detect_provider(agent) == 'gemini'

    def test_unknown(self) -> None:
        agent = _make_agent('a', _client('CustomClient'))
        router = ContextRouter()
        assert router._detect_provider(agent) == 'unknown'


# --- Same-provider (cache path) tests ---

class TestCachePath:
    """Verify same-provider routing passes history as-is."""

    @pytest.mark.asyncio
    async def test_same_provider_passthrough(self) -> None:
        client = _client('AnthropicClient')
        source = _make_agent('a', client)
        target = _make_agent('b', client)

        router = ContextRouter()
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'},
        ]

        result = await router.route(
            source, target, history, ctx,
        )
        assert result == history

    @pytest.mark.asyncio
    async def test_same_provider_records_context(
        self,
    ) -> None:
        client = _client('OpenAIClient')
        source = _make_agent('a', client)
        target = _make_agent('b', client)

        router = ContextRouter()
        ctx = ToolContext()
        history = [{'role': 'user', 'content': 'hi'}]

        await router.route(source, target, history, ctx)
        assert ctx.get('routing_path') == 'cache'
        assert ctx.get('source_provider') == 'openai'
        assert ctx.get('target_provider') == 'openai'


# --- Cross-provider (memory path) tests ---

class TestMemoryPath:
    """Verify cross-provider routing through pipeline."""

    @pytest.mark.asyncio
    async def test_cross_provider_with_pipeline(
        self,
    ) -> None:
        source = _make_agent(
            'a', _client('AnthropicClient'),
        )
        target = _make_agent(
            'b', _client('OpenAIClient'),
        )

        router = ContextRouter(pipeline=_FakePipeline())
        ctx = ToolContext()
        history = [{'role': 'user', 'content': 'hello'}]

        result = await router.route(
            source, target, history, ctx,
        )
        assert result == [
            {'role': 'user', 'content': 'HELLO'},
        ]
        assert ctx.get('routing_path') == 'memory'

    @pytest.mark.asyncio
    async def test_cross_provider_no_pipeline(
        self,
    ) -> None:
        source = _make_agent(
            'a', _client('AnthropicClient'),
        )
        target = _make_agent(
            'b', _client('GeminiClient'),
        )

        router = ContextRouter()
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'},
            {'role': 'system', 'content': 'you are helpful'},
        ]

        result = await router.route(
            source, target, history, ctx,
        )
        assert len(result) == 2
        assert all(
            m['role'] in ('user', 'system') for m in result
        )
        assert ctx.get('routing_path') == 'fallback'

    @pytest.mark.asyncio
    async def test_pipeline_error_fallback(self) -> None:
        source = _make_agent(
            'a', _client('AnthropicClient'),
        )
        target = _make_agent(
            'b', _client('OpenAIClient'),
        )

        router = ContextRouter(
            pipeline=_FailingPipeline(),
        )
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'bye'},
        ]

        result = await router.route(
            source, target, history, ctx,
        )
        assert len(result) == 1
        assert result[0]['role'] == 'user'
        assert ctx.get('routing_path') == 'fallback'

    @pytest.mark.asyncio
    async def test_unknown_provider_fallback(
        self,
    ) -> None:
        source = _make_agent(
            'a', _client('CustomClient'),
        )
        target = _make_agent(
            'b', _client('AnthropicClient'),
        )

        router = ContextRouter()
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'bye'},
        ]

        result = await router.route(
            source, target, history, ctx,
        )
        assert len(result) == 1
        assert ctx.get('routing_path') == 'fallback'
