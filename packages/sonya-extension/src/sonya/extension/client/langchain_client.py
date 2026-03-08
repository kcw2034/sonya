"""LangChainClient — wraps a LangChain ChatModel as sonya BaseClient."""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from sonya.core.client.base import BaseClient
from sonya.core.parsers.adapter import ParsedResponse, ParsedToolCall
from sonya.core.schemas.types import ClientConfig

from sonya.extension.schemas.types import (
    _check_langchain,
    langchain_to_sonya_messages,
    sonya_to_langchain_messages,
)


class LangChainClient(BaseClient):
    """Wraps a LangChain BaseChatModel as a sonya BaseClient.

    This allows using any LangChain-compatible model inside
    sonya's AgentRuntime and Runner.

    Args:
        langchain_model: A LangChain BaseChatModel instance.
        config: Optional ClientConfig override.
    """

    def __init__(
        self,
        langchain_model: Any,
        config: ClientConfig | None = None,
    ) -> None:
        _check_langchain()
        if config is None:
            model_name = getattr(
                langchain_model, 'model_name',
                getattr(langchain_model, 'model', 'langchain'),
            )
            config = ClientConfig(model=model_name)

        super().__init__(config)
        self._model = langchain_model

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        """Generate via LangChain model.

        Args:
            messages: List of sonya message dicts.
            **kwargs: Additional kwargs passed to the model.

        Returns:
            The LangChain AIMessage response.
        """
        lc_messages = sonya_to_langchain_messages(messages)

        tools = kwargs.pop('tools', None)
        if tools is not None:
            model = self._model.bind_tools(tools)
        else:
            model = self._model

        response = await model.ainvoke(lc_messages, **kwargs)
        return response

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Stream via LangChain model.

        Args:
            messages: List of sonya message dicts.
            **kwargs: Additional kwargs passed to the model.

        Yields:
            LangChain AIMessageChunk instances.
        """
        lc_messages = sonya_to_langchain_messages(messages)

        tools = kwargs.pop('tools', None)
        if tools is not None:
            model = self._model.bind_tools(tools)
        else:
            model = self._model

        async for chunk in model.astream(
            lc_messages, **kwargs
        ):
            yield chunk


class LangChainAdapter:
    """ResponseAdapter for LangChain AIMessage responses.

    Parses LangChain AIMessage into sonya's ParsedResponse format,
    enabling use with AgentRuntime.
    """

    def parse(self, response: Any) -> ParsedResponse:
        """Parse a LangChain AIMessage into ParsedResponse.

        Args:
            response: A LangChain AIMessage.

        Returns:
            Normalised ParsedResponse.
        """
        text = response.content or ''
        if isinstance(text, list):
            text = ''.join(
                block.get('text', '')
                for block in text
                if isinstance(block, dict)
                and block.get('type') == 'text'
            )

        tool_calls: list[ParsedToolCall] = []
        for tc in getattr(response, 'tool_calls', []):
            tool_calls.append(ParsedToolCall(
                id=tc.get('id', ''),
                name=tc['name'],
                arguments=tc.get('args', {}),
            ))

        stop_reason = 'tool_use' if tool_calls else 'end'

        return ParsedResponse(
            text=str(text),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response,
        )

    def format_generate_kwargs(
        self,
        instructions: str,
        tool_schemas: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build kwargs for LangChain generate.

        LangChain handles system prompt via messages, so we
        pass tool schemas for bind_tools.

        Args:
            instructions: System prompt (handled via messages).
            tool_schemas: Tool schemas to bind.

        Returns:
            Dict with 'tools' key if schemas provided.
        """
        kwargs: dict[str, Any] = {}
        if tool_schemas:
            kwargs['tools'] = tool_schemas
        return kwargs

    def format_assistant_message(
        self, response: Any,
    ) -> dict[str, Any]:
        """Format LangChain AIMessage as sonya history message.

        Args:
            response: A LangChain AIMessage.

        Returns:
            Sonya-format assistant message dict.
        """
        content = response.content or ''
        msg: dict[str, Any] = {
            'role': 'assistant',
            'content': str(content),
        }

        tool_calls = getattr(response, 'tool_calls', [])
        if tool_calls:
            msg['tool_calls'] = [
                {
                    'id': tc.get('id', ''),
                    'type': 'function',
                    'function': {
                        'name': tc['name'],
                        'arguments': (
                            tc['args']
                            if isinstance(tc['args'], str)
                            else _json.dumps(tc['args'])
                        ),
                    },
                }
                for tc in tool_calls
            ]

        return msg

    def format_tool_results_message(
        self, results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format tool results as sonya tool messages.

        Args:
            results: List of tool result dicts.

        Returns:
            List of sonya tool-role message dicts.
        """
        messages = []
        for r in results:
            messages.append({
                'role': 'tool',
                'tool_call_id': r['call_id'],
                'content': r.get(
                    'output', r.get('error', '')
                ),
            })
        return messages
