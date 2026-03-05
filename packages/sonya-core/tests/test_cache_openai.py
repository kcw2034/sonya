"""OpenAICache tests — usage-only, no CRUD."""

import pytest

from sonya.core.types import CacheConfig, CacheUsage
from sonya.core.context.cache.openai import OpenAICache
from unittest.mock import MagicMock


@pytest.fixture
def cache():
    return OpenAICache()


@pytest.mark.asyncio
async def test_create_raises(cache):
    with pytest.raises(NotImplementedError):
        await cache.create(CacheConfig(model='gpt-4o'))


@pytest.mark.asyncio
async def test_get_raises(cache):
    with pytest.raises(NotImplementedError):
        await cache.get('some-name')


@pytest.mark.asyncio
async def test_list_raises(cache):
    with pytest.raises(NotImplementedError):
        await cache.list()


@pytest.mark.asyncio
async def test_update_raises(cache):
    with pytest.raises(NotImplementedError):
        await cache.update('name', '3600s')


@pytest.mark.asyncio
async def test_delete_raises(cache):
    with pytest.raises(NotImplementedError):
        await cache.delete('name')


def test_parse_usage_with_cached_tokens():
    _response = MagicMock()
    _response.usage.prompt_tokens = 2048
    _details = MagicMock()
    _details.cached_tokens = 1024
    _response.usage.prompt_tokens_details = _details

    usage = OpenAICache.parse_usage(_response)
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 1024
    assert usage.total_input_tokens == 2048


def test_parse_usage_without_details():
    _response = MagicMock()
    _response.usage.prompt_tokens = 500
    _response.usage.prompt_tokens_details = None

    usage = OpenAICache.parse_usage(_response)
    assert usage.cached_tokens == 0
    assert usage.total_input_tokens == 500
