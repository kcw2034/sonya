"""Anthropic SDK thin wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

from sonya.core._types import ClientConfig
from sonya.core.client._base import BaseClient


class AnthropicClient(BaseClient):
    """anthropic.AsyncAnthropic 를 감싸는 thin wrapper.

    kwargs 는 messages.create() 에 그대로 패스스루된다.
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise ImportError(
                "anthropic 패키지가 필요합니다: pip install sonya-core[anthropic]"
            ) from e

        init_kwargs: dict[str, Any] = {}
        if config.api_key:
            init_kwargs["api_key"] = config.api_key
        self._sdk = AsyncAnthropic(**init_kwargs)

    async def _do_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        kwargs.setdefault("model", self._config.model)
        kwargs.setdefault("max_tokens", 1024)
        return await self._sdk.messages.create(messages=messages, **kwargs)

    async def _do_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        kwargs.setdefault("model", self._config.model)
        kwargs.setdefault("max_tokens", 1024)
        async with self._sdk.messages.stream(messages=messages, **kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self) -> None:
        await self._sdk.close()
