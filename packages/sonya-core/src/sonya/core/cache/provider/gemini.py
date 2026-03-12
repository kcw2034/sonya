"""Gemini context caching via google-genai SDK."""

from __future__ import annotations

from typing import Any

from sonya.core.schemas.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.cache.base import BaseCache


class GeminiCache(BaseCache):
    """Cache implementation using Gemini CachedContent API.

    Wraps the google-genai SDK's caches CRUD operations.
    """

    def __init__(
        self, api_key: str | None = None
    ) -> None:
        super().__init__(api_key=api_key)
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise ImportError(
                'google-genai package required: '
                'pip install sonya-core[gemini]'
            ) from e

        _init_kwargs: dict[str, Any] = {}
        if api_key:
            _init_kwargs['api_key'] = api_key
        self._sdk = genai.Client(**_init_kwargs)
        self._types = types

    def _to_cached_content(
        self, raw: Any
    ) -> CachedContent:
        """Convert SDK response to CachedContent.

        Args:
            raw: Native google-genai cache object.

        Returns:
            Unified CachedContent dataclass.
        """
        return CachedContent(
            name=raw.name,
            model=raw.model,
            display_name=raw.display_name,
            create_time=raw.create_time,
            expire_time=raw.expire_time,
            token_count=(
                raw.usage_metadata.total_token_count
            ),
            provider='gemini',
        )

    async def create(
        self, config: CacheConfig
    ) -> CachedContent:
        """Create a Gemini CachedContent resource.

        Args:
            config: Cache creation parameters.

        Returns:
            The created cache resource.
        """
        _create_config = (
            self._types.CreateCachedContentConfig(
                contents=config.contents,
                system_instruction=(
                    config.system_instruction
                ),
                display_name=config.display_name,
                ttl=config.ttl,
                tools=config.tools or None,
            )
        )
        _raw = await self._sdk.aio.caches.create(
            model=config.model,
            config=_create_config,
        )
        return self._to_cached_content(_raw)

    async def get(self, name: str) -> CachedContent:
        """Retrieve a Gemini cache entry.

        Args:
            name: Cache resource name.

        Returns:
            The cached content resource.
        """
        _raw = await self._sdk.aio.caches.get(
            name=name
        )
        return self._to_cached_content(_raw)

    async def list(self) -> list[CachedContent]:
        """List all Gemini cache entries.

        Returns:
            List of cached content resources.
        """
        _results: list[CachedContent] = []
        async for _raw in (
            self._sdk.aio.caches.list()
        ):
            _results.append(
                self._to_cached_content(_raw)
            )
        return _results

    async def update(
        self, name: str, ttl: str
    ) -> CachedContent:
        """Update a Gemini cache entry's TTL.

        Args:
            name: Cache resource name.
            ttl: New time-to-live (e.g. '7200s').

        Returns:
            The updated cache resource.
        """
        _update_config = (
            self._types.UpdateCachedContentConfig(
                ttl=ttl
            )
        )
        _raw = await self._sdk.aio.caches.update(
            name=name,
            config=_update_config,
        )
        return self._to_cached_content(_raw)

    async def delete(self, name: str) -> None:
        """Delete a Gemini cache entry.

        Args:
            name: Cache resource name.
        """
        await self._sdk.aio.caches.delete(name=name)

    @staticmethod
    def parse_usage(response: Any) -> CacheUsage:
        """Extract cache usage from Gemini response.

        Args:
            response: Native Gemini response object.

        Returns:
            Unified cache usage metrics.
        """
        _meta = response.usage_metadata
        return CacheUsage(
            cached_tokens=getattr(
                _meta, 'cached_content_token_count', 0
            ),
            total_input_tokens=getattr(
                _meta, 'prompt_token_count', 0
            ),
        )
