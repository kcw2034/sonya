"""Google Gemini (google-genai) SDK thin wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

from sonya.core.schemas.types import ClientConfig
from sonya.core.client.provider.base import BaseClient


class GeminiClient(BaseClient):
    """Thin wrapper around google.genai.Client.

    kwargs are converted to GenerateContentConfig
    and passed through.
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)
        try:
            from google import genai
            from google.genai.types import (
                GenerateContentConfig,
            )
        except ImportError as e:
            raise ImportError(
                'google-genai package required: '
                'pip install sonya-core[gemini]'
            ) from e

        self._sdk = genai.Client(
            **self._build_init_kwargs()
        )
        self._generate_content_config = (
            GenerateContentConfig
        )

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        _config = (
            self._generate_content_config(**kwargs)
            if kwargs
            else None
        )
        return await self._sdk.aio.models.generate_content(
            model=self._config.model,
            contents=messages,
            config=_config,
        )

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        _config = (
            self._generate_content_config(**kwargs)
            if kwargs
            else None
        )
        async for chunk in (
            await self._sdk.aio.models.generate_content_stream(
                model=self._config.model,
                contents=messages,
                config=_config,
            )
        ):
            yield chunk
