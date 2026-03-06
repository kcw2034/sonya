"""Anthropic prompt caching — local config + cache_control."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sonya.core.schemas.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.client.cache_base import BaseCache


class AnthropicCache(BaseCache):
    """Cache implementation for Anthropic prompt caching.

    Anthropic caching is stateless and request-scoped.
    This class stores configs locally and provides
    build_cache_control() for injecting cache hints
    into API requests.
    """

    def __init__(
        self, api_key: str | None = None
    ) -> None:
        super().__init__(api_key=api_key)
        self._store: dict[str, _CacheEntry] = {}

    async def create(
        self, config: CacheConfig
    ) -> CachedContent:
        """Store a cache config locally.

        Args:
            config: Cache creation parameters.

        Returns:
            A locally-generated CachedContent reference.
        """
        _name = (
            f'anthropic-cache-{uuid.uuid4().hex[:8]}'
        )
        _now = datetime.now(timezone.utc).isoformat()
        self._store[_name] = _CacheEntry(
            config=config, name=_name
        )
        return CachedContent(
            name=_name,
            model=config.model,
            display_name=config.display_name,
            create_time=_now,
            provider='anthropic',
        )

    async def get(self, name: str) -> CachedContent:
        """Retrieve a locally stored cache config.

        Args:
            name: Local cache identifier.

        Returns:
            The cached content reference.

        Raises:
            KeyError: If name is not found.
        """
        _entry = self._store[name]
        return CachedContent(
            name=name,
            model=_entry.config.model,
            display_name=_entry.config.display_name,
            provider='anthropic',
        )

    async def list(self) -> list[CachedContent]:
        """List all locally stored cache configs.

        Returns:
            List of cached content references.
        """
        _results: list[CachedContent] = []
        for _name, _entry in self._store.items():
            _results.append(
                CachedContent(
                    name=_name,
                    model=_entry.config.model,
                    display_name=(
                        _entry.config.display_name
                    ),
                    provider='anthropic',
                )
            )
        return _results

    async def update(
        self, name: str, ttl: str
    ) -> CachedContent:
        """Update TTL of a local cache config.

        Args:
            name: Local cache identifier.
            ttl: New TTL value (e.g. '5m', '1h').

        Returns:
            The updated cached content reference.

        Raises:
            KeyError: If name is not found.
        """
        _entry = self._store[name]
        _new_config = CacheConfig(
            model=_entry.config.model,
            display_name=_entry.config.display_name,
            system_instruction=(
                _entry.config.system_instruction
            ),
            contents=_entry.config.contents,
            tools=_entry.config.tools,
            ttl=ttl,
        )
        self._store[name] = _CacheEntry(
            config=_new_config, name=name
        )
        return CachedContent(
            name=name,
            model=_new_config.model,
            display_name=_new_config.display_name,
            provider='anthropic',
        )

    async def delete(self, name: str) -> None:
        """Remove a local cache config.

        Args:
            name: Local cache identifier.

        Raises:
            KeyError: If name is not found.
        """
        del self._store[name]

    def build_cache_control(
        self, ttl: str | None = None
    ) -> dict[str, str]:
        """Build a cache_control dict for API requests.

        Args:
            ttl: Optional TTL override ('5m' or '1h').

        Returns:
            Dict suitable for cache_control parameter.
        """
        _control: dict[str, str] = {
            'type': 'ephemeral'
        }
        if ttl:
            _control['ttl'] = ttl
        return _control

    @staticmethod
    def parse_usage(response: Any) -> CacheUsage:
        """Extract cache usage from Anthropic response.

        Args:
            response: Native Anthropic response object.

        Returns:
            Unified cache usage metrics.
        """
        _usage = response.usage
        _input = getattr(_usage, 'input_tokens', 0)
        _creation = getattr(
            _usage, 'cache_creation_input_tokens', 0
        )
        _read = getattr(
            _usage, 'cache_read_input_tokens', 0
        )
        return CacheUsage(
            cached_tokens=_read,
            cache_creation_tokens=_creation,
            total_input_tokens=(
                _input + _creation + _read
            ),
        )


class _CacheEntry:
    """Internal storage entry for a cache config."""

    __slots__ = ('config', 'name')

    def __init__(
        self, config: CacheConfig, name: str
    ) -> None:
        self.config = config
        self.name = name
