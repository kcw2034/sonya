"""BaseCache ABC -- base for all provider cache implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sonya.core.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)


class BaseCache(ABC):
    """Abstract base for provider cache operations.

    Subclasses implement CRUD methods and parse_usage.
    Providers that do not support explicit cache
    management should raise NotImplementedError.
    """

    def __init__(
        self, api_key: str | None = None
    ) -> None:
        self._api_key = api_key

    @abstractmethod
    async def create(
        self, config: CacheConfig
    ) -> CachedContent:
        """Create a new cache entry.

        Args:
            config: Cache creation parameters.

        Returns:
            The created cache resource.
        """

    @abstractmethod
    async def get(self, name: str) -> CachedContent:
        """Retrieve a cache entry by name.

        Args:
            name: Provider-specific cache identifier.

        Returns:
            The cached content resource.
        """

    @abstractmethod
    async def list(self) -> list[CachedContent]:
        """List all cache entries.

        Returns:
            List of cached content resources.
        """

    @abstractmethod
    async def update(
        self, name: str, ttl: str
    ) -> CachedContent:
        """Update a cache entry's TTL.

        Args:
            name: Provider-specific cache identifier.
            ttl: New time-to-live string.

        Returns:
            The updated cache resource.
        """

    @abstractmethod
    async def delete(self, name: str) -> None:
        """Delete a cache entry.

        Args:
            name: Provider-specific cache identifier.
        """

    @staticmethod
    @abstractmethod
    def parse_usage(response: Any) -> CacheUsage:
        """Extract cache usage from a provider response.

        Args:
            response: Native SDK response object.

        Returns:
            Unified cache usage metrics.
        """
