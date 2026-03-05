"""Cache type dataclass tests."""

import pytest

from sonya.core.types import CacheConfig, CachedContent, CacheUsage


def test_cache_config_defaults():
    config = CacheConfig(model='gemini-2.0-flash-001')
    assert config.model == 'gemini-2.0-flash-001'
    assert config.display_name is None
    assert config.system_instruction is None
    assert config.contents == []
    assert config.tools == []
    assert config.ttl is None


def test_cache_config_full():
    config = CacheConfig(
        model='claude-sonnet-4-6',
        display_name='My Cache',
        system_instruction='Be helpful.',
        contents=[{'role': 'user', 'content': 'hi'}],
        tools=[{'name': 'search'}],
        ttl='3600s',
    )
    assert config.display_name == 'My Cache'
    assert config.ttl == '3600s'
    assert len(config.contents) == 1


def test_cache_config_is_frozen():
    config = CacheConfig(model='test')
    with pytest.raises(AttributeError):
        config.model = 'other'


def test_cached_content_defaults():
    content = CachedContent(name='cache-123', model='gpt-4o')
    assert content.name == 'cache-123'
    assert content.model == 'gpt-4o'
    assert content.display_name is None
    assert content.create_time is None
    assert content.expire_time is None
    assert content.token_count is None
    assert content.provider == ''


def test_cached_content_full():
    content = CachedContent(
        name='cachedContents/abc',
        model='gemini-2.0-flash-001',
        display_name='My Cache',
        create_time='2026-03-05T00:00:00Z',
        expire_time='2026-03-05T01:00:00Z',
        token_count=5000,
        provider='gemini',
    )
    assert content.provider == 'gemini'
    assert content.token_count == 5000


def test_cache_usage_defaults():
    usage = CacheUsage()
    assert usage.cached_tokens == 0
    assert usage.cache_creation_tokens == 0
    assert usage.total_input_tokens == 0


def test_cache_usage_values():
    usage = CacheUsage(
        cached_tokens=1024,
        cache_creation_tokens=0,
        total_input_tokens=2048,
    )
    assert usage.cached_tokens == 1024
    assert usage.total_input_tokens == 2048
