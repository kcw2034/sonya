"""Google Gemini (google-genai) SDK thin wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

from sonya.core._types import ClientConfig
from sonya.core.client._base import BaseClient


class GeminiClient(BaseClient):
    """google.genai.Client 를 감싸는 thin wrapper.

    kwargs 는 GenerateContentConfig 로 변환되어 패스스루된다.
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)
        try:
            from google import genai
        except ImportError as e:
            raise ImportError(
                "google-genai 패키지가 필요합니다: pip install sonya-core[gemini]"
            ) from e

        init_kwargs: dict[str, Any] = {}
        if config.api_key:
            init_kwargs["api_key"] = config.api_key
        self._sdk = genai.Client(**init_kwargs)

    async def _do_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        from google.genai import types

        config = types.GenerateContentConfig(**kwargs) if kwargs else None
        return await self._sdk.aio.models.generate_content(
            model=self._config.model,
            contents=messages,
            config=config,
        )

    async def _do_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        from google.genai import types

        config = types.GenerateContentConfig(**kwargs) if kwargs else None
        async for chunk in await self._sdk.aio.models.generate_content_stream(
            model=self._config.model,
            contents=messages,
            config=config,
        ):
            yield chunk
