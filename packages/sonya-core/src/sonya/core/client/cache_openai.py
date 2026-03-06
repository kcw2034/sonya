"""OpenAI automatic caching — usage observation only."""

from __future__ import annotations

from typing import Any

from sonya.core.schemas.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.client.cache_base import BaseCache

_UNSUPPORTED_MSG = (
    'OpenAI does not support explicit'
    ' cache management'
)


class OpenAICache(BaseCache):
    """Cache implementation for OpenAI automatic caching.

    OpenAI caching is fully automatic. CRUD operations
    are not supported. Only parse_usage() extracts
    cache hit information from responses.
    """

    def __init__(
        self, api_key: str | None = None
    ) -> None:
        super().__init__(api_key=api_key)

    async def create(
        self, config: CacheConfig
    ) -> CachedContent:
        """Not supported by OpenAI.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(_UNSUPPORTED_MSG)

    async def get(self, name: str) -> CachedContent:
        """Not supported by OpenAI.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(_UNSUPPORTED_MSG)

    async def list(self) -> list[CachedContent]:
        """Not supported by OpenAI.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(_UNSUPPORTED_MSG)

    async def update(
        self, name: str, ttl: str
    ) -> CachedContent:
        """Not supported by OpenAI.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(_UNSUPPORTED_MSG)

    async def delete(self, name: str) -> None:
        """Not supported by OpenAI.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(_UNSUPPORTED_MSG)

    @staticmethod
    def parse_usage(response: Any) -> CacheUsage:
        """Extract cache usage from OpenAI response.

        Args:
            response: Native OpenAI response object.

        Returns:
            Unified cache usage metrics.
        """
        _usage = response.usage
        _prompt = getattr(_usage, 'prompt_tokens', 0)
        _details = getattr(
            _usage, 'prompt_tokens_details', None
        )
        _cached = (
            getattr(_details, 'cached_tokens', 0)
            if _details
            else 0
        )
        return CacheUsage(
            cached_tokens=_cached,
            total_input_tokens=_prompt,
        )
