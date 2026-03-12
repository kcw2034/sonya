"""Tests for LangChainClient and LangChainAdapter."""

from __future__ import annotations

from typing import Any, List, Optional

import pytest

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import (
    BaseChatModel,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from sonya.core.parsers.adapter import ParsedResponse
from sonya.core.schemas.types import ClientConfig

from sonya.extension import LangChainAdapter, LangChainClient


class _MockChatModel(BaseChatModel):
    """Minimal mock LangChain ChatModel for testing."""

    model_name: str = 'mock-model'

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[
            CallbackManagerForLLMRun
        ] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content='mock response'
                    )
                )
            ]
        )

    @property
    def _llm_type(self) -> str:
        return 'mock'


class TestLangChainClient:
    """Tests for LangChainClient wrapping BaseChatModel."""

    def test_init_auto_config(self) -> None:
        """Client auto-detects model name from ChatModel."""
        mock = _MockChatModel()
        client = LangChainClient(mock)
        assert client._config.model == 'mock-model'

    def test_init_custom_config(self) -> None:
        """Client accepts custom ClientConfig."""
        mock = _MockChatModel()
        config = ClientConfig(model='custom-model')
        client = LangChainClient(mock, config=config)
        assert client._config.model == 'custom-model'

    @pytest.mark.asyncio
    async def test_generate(self) -> None:
        """Client generates via LangChain model."""
        mock = _MockChatModel()
        client = LangChainClient(mock)

        messages = [
            {'role': 'user', 'content': 'Hello'},
        ]
        response = await client.generate(messages)

        assert isinstance(response, AIMessage)
        assert response.content == 'mock response'


class TestLangChainAdapter:
    """Tests for LangChainAdapter response parsing."""

    def test_parse_text_response(self) -> None:
        """Adapter parses text-only AIMessage."""
        adapter = LangChainAdapter()
        msg = AIMessage(content='Hello world')
        parsed = adapter.parse(msg)

        assert isinstance(parsed, ParsedResponse)
        assert parsed.text == 'Hello world'
        assert parsed.tool_calls == []
        assert parsed.stop_reason == 'end'

    def test_parse_tool_call_response(self) -> None:
        """Adapter parses AIMessage with tool calls."""
        adapter = LangChainAdapter()
        msg = AIMessage(
            content='',
            tool_calls=[{
                'name': 'search',
                'args': {'query': 'test'},
                'id': 'call_1',
                'type': 'tool_call',
            }],
        )

        parsed = adapter.parse(msg)

        assert parsed.stop_reason == 'tool_use'
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == 'search'
        assert parsed.tool_calls[0].id == 'call_1'

    def test_format_assistant_message(self) -> None:
        """Adapter formats AIMessage as sonya dict."""
        adapter = LangChainAdapter()
        msg = AIMessage(content='Hi')
        result = adapter.format_assistant_message(msg)

        assert result['role'] == 'assistant'
        assert result['content'] == 'Hi'

    def test_format_tool_results(self) -> None:
        """Adapter formats tool results as messages."""
        adapter = LangChainAdapter()
        results = [
            {
                'call_id': 'call_1',
                'name': 'search',
                'output': 'found it',
                'success': True,
            },
        ]
        msgs = adapter.format_tool_results_message(results)

        assert len(msgs) == 1
        assert msgs[0]['role'] == 'tool'
        assert msgs[0]['tool_call_id'] == 'call_1'
        assert msgs[0]['content'] == 'found it'
