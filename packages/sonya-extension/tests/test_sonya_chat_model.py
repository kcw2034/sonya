"""Tests for SonyaChatModel wrapping sonya BaseClient."""

from __future__ import annotations

from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from langchain_core.messages import AIMessage, HumanMessage

from sonya.core.client.provider.base import BaseClient
from sonya.core.parsers.adapter import (
    _ADAPTER_MAP,
    AnthropicAdapter,
)
from sonya.core.schemas.types import ClientConfig

from sonya.extension import SonyaChatModel


class _MockAnthropicResponse:
    """Simulates an Anthropic API response."""

    def __init__(self, text: str) -> None:
        self.content = [
            MagicMock(type='text', text=text)
        ]
        self.stop_reason = 'end_turn'


class _MockAnthropicClient(BaseClient):
    """Mock sonya client that mimics AnthropicClient."""

    def __init__(self) -> None:
        super().__init__(
            ClientConfig(model='claude-test')
        )
        self._response_text = 'mock sonya response'

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        return _MockAnthropicResponse(
            self._response_text
        )


# Register mock client in adapter map for testing
_ADAPTER_MAP['_MockAnthropicClient'] = AnthropicAdapter


class TestSonyaChatModel:
    """Tests for SonyaChatModel."""

    def test_creates_instance(self) -> None:
        """SonyaChatModel creates a BaseChatModel."""
        from langchain_core.language_models.chat_models \
            import BaseChatModel

        client = _MockAnthropicClient()
        model = SonyaChatModel(sonya_client=client)

        assert isinstance(model, BaseChatModel)

    def test_llm_type(self) -> None:
        """Model reports correct LLM type."""
        client = _MockAnthropicClient()
        model = SonyaChatModel(sonya_client=client)
        assert '_MockAnthropicClient' in model._llm_type

    @pytest.mark.asyncio
    async def test_ainvoke(self) -> None:
        """Model generates via sonya client."""
        client = _MockAnthropicClient()
        model = SonyaChatModel(sonya_client=client)

        result = await model.ainvoke([
            HumanMessage(content='Hello'),
        ])

        assert isinstance(result, AIMessage)
        assert result.content == 'mock sonya response'
