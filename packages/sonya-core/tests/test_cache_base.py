"""BaseCache ABC tests."""

from typing import Any

import pytest

from sonya.core.schemas.types import CacheConfig, CachedContent, CacheUsage
from sonya.core.cache.base import BaseCache


class DummyCache(BaseCache):
    """Minimal concrete implementation for testing."""

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)
        self._store: dict[str, CachedContent] = {}

    async def create(
        self, config: CacheConfig
    ) -> CachedContent:
        _content = CachedContent(
            name='dummy-1',
            model=config.model,
            display_name=config.display_name,
            provider='dummy',
        )
        self._store[_content.name] = _content
        return _content

    async def get(self, name: str) -> CachedContent:
        return self._store[name]

    async def list(self) -> list[CachedContent]:
        return list(self._store.values())

    async def update(
        self, name: str, ttl: str
    ) -> CachedContent:
        return self._store[name]

    async def delete(self, name: str) -> None:
        del self._store[name]

    @staticmethod
    def parse_usage(response: Any) -> CacheUsage:
        return CacheUsage(cached_tokens=100)


@pytest.mark.asyncio
async def test_create_returns_cached_content():
    cache = DummyCache()
    config = CacheConfig(model='test-model')
    result = await cache.create(config)
    assert isinstance(result, CachedContent)
    assert result.name == 'dummy-1'
    assert result.model == 'test-model'


@pytest.mark.asyncio
async def test_get_returns_created_content():
    cache = DummyCache()
    await cache.create(CacheConfig(model='test'))
    result = await cache.get('dummy-1')
    assert result.name == 'dummy-1'


@pytest.mark.asyncio
async def test_list_returns_all():
    cache = DummyCache()
    await cache.create(CacheConfig(model='test'))
    items = await cache.list()
    assert len(items) == 1


@pytest.mark.asyncio
async def test_delete_removes_entry():
    cache = DummyCache()
    await cache.create(CacheConfig(model='test'))
    await cache.delete('dummy-1')
    items = await cache.list()
    assert len(items) == 0


def test_parse_usage_returns_cache_usage():
    usage = DummyCache.parse_usage({'some': 'response'})
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 100


def test_base_cache_stores_api_key():
    cache = DummyCache(api_key='test-key')
    assert cache._api_key == 'test-key'


def test_base_cache_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseCache()
