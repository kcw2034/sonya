"""AnthropicCache tests — local config storage + cache_control."""

import pytest

from sonya.core.schemas.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.client.cache_anthropic import (
    AnthropicCache,
)
from unittest.mock import MagicMock


@pytest.fixture
def cache():
    return AnthropicCache()


@pytest.mark.asyncio
async def test_create_stores_locally(cache):
    config = CacheConfig(
        model='claude-sonnet-4-6',
        display_name='My Prompt Cache',
        system_instruction='Be helpful.',
        ttl='5m',
    )
    result = await cache.create(config)

    assert isinstance(result, CachedContent)
    assert result.provider == 'anthropic'
    assert result.model == 'claude-sonnet-4-6'
    assert result.display_name == 'My Prompt Cache'
    assert result.name.startswith('anthropic-cache-')


@pytest.mark.asyncio
async def test_get_returns_stored(cache):
    config = CacheConfig(model='claude-sonnet-4-6')
    created = await cache.create(config)
    result = await cache.get(created.name)
    assert result.name == created.name


@pytest.mark.asyncio
async def test_get_raises_on_missing(cache):
    with pytest.raises(KeyError):
        await cache.get('nonexistent')


@pytest.mark.asyncio
async def test_list_returns_all(cache):
    await cache.create(CacheConfig(model='a'))
    await cache.create(CacheConfig(model='b'))
    items = await cache.list()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_update_changes_ttl(cache):
    created = await cache.create(
        CacheConfig(model='test', ttl='5m')
    )
    updated = await cache.update(created.name, '1h')
    assert updated.name == created.name


@pytest.mark.asyncio
async def test_delete_removes(cache):
    created = await cache.create(
        CacheConfig(model='test')
    )
    await cache.delete(created.name)
    items = await cache.list()
    assert len(items) == 0


def test_build_cache_control_ephemeral():
    cache = AnthropicCache()
    result = cache.build_cache_control()
    assert result == {'type': 'ephemeral'}


def test_build_cache_control_with_ttl():
    cache = AnthropicCache()
    result = cache.build_cache_control(ttl='1h')
    assert result == {'type': 'ephemeral', 'ttl': '1h'}


def test_parse_usage():
    _response = MagicMock()
    _response.usage.input_tokens = 500
    _response.usage.cache_creation_input_tokens = 1000
    _response.usage.cache_read_input_tokens = 2000

    usage = AnthropicCache.parse_usage(_response)
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 2000
    assert usage.cache_creation_tokens == 1000
    assert usage.total_input_tokens == 3500
