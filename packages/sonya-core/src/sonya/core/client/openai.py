"""OpenAI SDK thin wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

from sonya.core._types import ClientConfig
from sonya.core.client._base import BaseClient


class OpenAIClient(BaseClient):
    """openai.AsyncOpenAI 를 감싸는 thin wrapper.

    kwargs 는 chat.completions.create() 에 그대로 패스스루된다.
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "openai 패키지가 필요합니다: pip install sonya-core[openai]"
            ) from e

        init_kwargs: dict[str, Any] = {}
        if config.api_key:
            init_kwargs["api_key"] = config.api_key
        self._sdk = AsyncOpenAI(**init_kwargs)

    async def _do_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        kwargs.setdefault("model", self._config.model)
        return await self._sdk.chat.completions.create(messages=messages, **kwargs)

    async def _do_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        kwargs.setdefault("model", self._config.model)
        stream = await self._sdk.chat.completions.create(
            messages=messages, stream=True, **kwargs
        )
        async for chunk in stream:
            yield chunk

    async def close(self) -> None:
        await self._sdk.close()
