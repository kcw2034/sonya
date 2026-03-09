"""GeminiCache tests with mocked google-genai SDK."""

import pytest

from unittest.mock import AsyncMock, MagicMock, patch
from sonya.core.schemas.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.client.cache.gemini import GeminiCache


@pytest.fixture
def mock_sdk():
    """Create a mock google-genai client."""
    _client = MagicMock()
    _client.aio.caches.create = AsyncMock()
    _client.aio.caches.get = AsyncMock()
    _client.aio.caches.list = MagicMock()
    _client.aio.caches.update = AsyncMock()
    _client.aio.caches.delete = AsyncMock()
    return _client


@pytest.fixture
def cache(mock_sdk):
    """Create GeminiCache with mocked SDK."""
    _cache = GeminiCache.__new__(GeminiCache)
    _cache._api_key = None
    _cache._sdk = mock_sdk
    _cache._types = MagicMock()
    return _cache


def _make_raw_cache(
    name: str = 'cachedContents/abc',
    model: str = 'gemini-2.0-flash-001',
    display_name: str | None = 'Test',
    create_time: str | None = '2026-03-05T00:00:00Z',
    expire_time: str | None = '2026-03-05T01:00:00Z',
    token_count: int = 5000,
) -> MagicMock:
    """Build a mock SDK cache response."""
    _raw = MagicMock()
    _raw.name = name
    _raw.model = model
    _raw.display_name = display_name
    _raw.create_time = create_time
    _raw.expire_time = expire_time
    _raw.usage_metadata.total_token_count = token_count
    return _raw


@pytest.mark.asyncio
async def test_create(cache, mock_sdk):
    mock_sdk.aio.caches.create.return_value = (
        _make_raw_cache()
    )
    config = CacheConfig(
        model='gemini-2.0-flash-001',
        display_name='Test',
        ttl='3600s',
    )
    result = await cache.create(config)

    assert isinstance(result, CachedContent)
    assert result.name == 'cachedContents/abc'
    assert result.provider == 'gemini'
    assert result.token_count == 5000
    mock_sdk.aio.caches.create.assert_called_once()


@pytest.mark.asyncio
async def test_get(cache, mock_sdk):
    mock_sdk.aio.caches.get.return_value = (
        _make_raw_cache()
    )
    result = await cache.get('cachedContents/abc')
    assert result.name == 'cachedContents/abc'
    assert result.provider == 'gemini'
    mock_sdk.aio.caches.get.assert_called_once_with(
        name='cachedContents/abc'
    )


@pytest.mark.asyncio
async def test_list(cache, mock_sdk):
    async def _mock_list():
        for item in [
            _make_raw_cache(),
            _make_raw_cache(name='cachedContents/def'),
        ]:
            yield item

    mock_sdk.aio.caches.list.return_value = (
        _mock_list()
    )
    results = await cache.list()
    assert len(results) == 2
    assert results[0].provider == 'gemini'


@pytest.mark.asyncio
async def test_update(cache, mock_sdk):
    mock_sdk.aio.caches.update.return_value = (
        _make_raw_cache()
    )
    result = await cache.update(
        'cachedContents/abc', '7200s'
    )
    assert isinstance(result, CachedContent)
    mock_sdk.aio.caches.update.assert_called_once()


@pytest.mark.asyncio
async def test_delete(cache, mock_sdk):
    mock_sdk.aio.caches.delete.return_value = None
    await cache.delete('cachedContents/abc')
    mock_sdk.aio.caches.delete.assert_called_once_with(
        name='cachedContents/abc'
    )


def test_parse_usage():
    _response = MagicMock()
    _response.usage_metadata.prompt_token_count = 2048
    _response.usage_metadata.cached_content_token_count = 1024

    usage = GeminiCache.parse_usage(_response)
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 1024
    assert usage.total_input_tokens == 2048


def test_parse_usage_missing_fields():
    _response = MagicMock(spec=[])
    _response.usage_metadata = MagicMock(spec=[])
    usage = GeminiCache.parse_usage(_response)
    assert usage.cached_tokens == 0
    assert usage.total_input_tokens == 0
