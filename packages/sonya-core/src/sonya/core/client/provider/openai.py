"""OpenAI SDK thin wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

from sonya.core.schemas.types import ClientConfig
from sonya.core.client.provider.base import BaseClient


class OpenAIClient(BaseClient):
    """Thin wrapper around openai.AsyncOpenAI.

    kwargs are passed through to
    chat.completions.create().
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                'openai package required: '
                'pip install sonya-core[openai]'
            ) from e

        self._sdk = AsyncOpenAI(
            **self._build_init_kwargs()
        )

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        kwargs.setdefault('model', self._config.model)
        return await self._sdk.chat.completions.create(
            messages=messages, **kwargs
        )

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        kwargs.setdefault('model', self._config.model)
        _stream = (
            await self._sdk.chat.completions.create(
                messages=messages,
                stream=True,
                **kwargs,
            )
        )
        async for chunk in _stream:
            yield chunk

    async def close(self) -> None:
        """Release the underlying SDK resources."""
        await self._sdk.close()
