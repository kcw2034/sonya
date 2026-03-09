"""Anthropic SDK thin wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

from sonya.core.schemas.types import ClientConfig
from sonya.core.client.provider.base import BaseClient


class AnthropicClient(BaseClient):
    """Thin wrapper around anthropic.AsyncAnthropic.

    kwargs are passed through to messages.create().
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise ImportError(
                'anthropic package required: '
                'pip install sonya-core[anthropic]'
            ) from e

        self._sdk = AsyncAnthropic(
            **self._build_init_kwargs()
        )

    def _apply_defaults(
        self, kwargs: dict[str, Any]
    ) -> None:
        """Set Anthropic-specific default kwargs."""
        kwargs.setdefault('model', self._config.model)
        kwargs.setdefault('max_tokens', 1024)

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        self._apply_defaults(kwargs)
        return await self._sdk.messages.create(
            messages=messages, **kwargs
        )

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        self._apply_defaults(kwargs)
        async with self._sdk.messages.stream(
            messages=messages, **kwargs
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self) -> None:
        """Release the underlying SDK resources."""
        await self._sdk.close()
