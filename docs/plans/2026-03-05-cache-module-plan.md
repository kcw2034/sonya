# Cache Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a unified cache abstraction layer wrapping Anthropic prompt caching, Gemini context caching, and OpenAI automatic caching behind a single BaseCache ABC.

**Architecture:** BaseCache ABC in `context/cache/base.py` defines CRUD operations (create/get/list/update/delete) plus a static `parse_usage()` method. Three provider implementations: GeminiCache (native CRUD), AnthropicCache (local config storage + cache_control injection), OpenAICache (NotImplementedError for CRUD, parse_usage only). Types live in `core/types.py`.

**Tech Stack:** Python 3.11+, abc, dataclasses, google-genai (optional), anthropic (optional), openai (optional)

---

### Task 1: Extend types.py with cache data models

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/types.py:92-98`
- Test: `packages/sonya-core/tests/test_cache_types.py`

**Step 1: Write failing test for CacheConfig, CachedContent, CacheUsage**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_types.py -v`
Expected: FAIL — CacheConfig signature mismatch, CachedContent/CacheUsage not found

**Step 3: Replace CacheConfig and add CachedContent, CacheUsage in types.py**

Replace the existing `CacheConfig` (lines 92-98) with:

```python
@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Input configuration for cache creation.

    Args:
        model: Target LLM model identifier.
        display_name: Human-readable cache label.
        system_instruction: System prompt to cache.
        contents: Message dicts to cache.
        tools: Tool definitions to cache.
        ttl: Time-to-live string (e.g. '3600s', '5m').
    """

    model: str
    display_name: str | None = None
    system_instruction: str | None = None
    contents: list[dict[str, Any]] = field(
        default_factory=list
    )
    tools: list[dict[str, Any]] = field(
        default_factory=list
    )
    ttl: str | None = None


@dataclass(frozen=True, slots=True)
class CachedContent:
    """Unified cache resource returned by create/get.

    Args:
        name: Provider-specific cache identifier.
        model: Model this cache is bound to.
        display_name: Human-readable label.
        create_time: ISO 8601 creation timestamp.
        expire_time: ISO 8601 expiration timestamp.
        token_count: Total cached token count.
        provider: Provider name (anthropic/gemini/openai).
    """

    name: str
    model: str
    display_name: str | None = None
    create_time: str | None = None
    expire_time: str | None = None
    token_count: int | None = None
    provider: str = ''


@dataclass(frozen=True, slots=True)
class CacheUsage:
    """Cache token usage extracted from a response.

    Args:
        cached_tokens: Tokens served from cache.
        cache_creation_tokens: Tokens written to cache.
        total_input_tokens: Total input tokens consumed.
    """

    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    total_input_tokens: int = 0
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_types.py -v`
Expected: All 7 tests PASS

**Step 5: Run existing tests for regression**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/ -v`
Expected: All existing tests still PASS

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/types.py packages/sonya-core/tests/test_cache_types.py
git commit -m "feat: add CachedContent and CacheUsage types, extend CacheConfig"
```

---

### Task 2: Create BaseCache ABC

**Files:**
- Create: `packages/sonya-core/src/sonya/core/context/__init__.py`
- Create: `packages/sonya-core/src/sonya/core/context/cache/__init__.py`
- Create: `packages/sonya-core/src/sonya/core/context/cache/base.py`
- Test: `packages/sonya-core/tests/test_cache_base.py`

**Step 1: Write failing test for BaseCache**

```python
"""BaseCache ABC tests."""

import pytest

from sonya.core.types import CacheConfig, CachedContent, CacheUsage
from sonya.core.context.cache.base import BaseCache
from typing import Any


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
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_base.py -v`
Expected: FAIL — `sonya.core.context.cache.base` not found

**Step 3: Create directory structure and BaseCache**

Create `packages/sonya-core/src/sonya/core/context/__init__.py`:

```python
"""Context management modules."""
```

Create `packages/sonya-core/src/sonya/core/context/cache/__init__.py`:

```python
"""Cache provider re-exports."""

from sonya.core.context.cache.base import BaseCache

__all__ = [
    'BaseCache',
]
```

Create `packages/sonya-core/src/sonya/core/context/cache/base.py`:

```python
"""BaseCache ABC — base for all provider cache implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sonya.core.types import CacheConfig, CachedContent, CacheUsage


class BaseCache(ABC):
    """Abstract base for provider cache operations.

    Subclasses implement CRUD methods and parse_usage.
    Providers that do not support explicit cache management
    should raise NotImplementedError in unsupported methods.
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
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_base.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/ packages/sonya-core/tests/test_cache_base.py
git commit -m "feat: add BaseCache ABC with CRUD interface"
```

---

### Task 3: Implement GeminiCache

**Files:**
- Create: `packages/sonya-core/src/sonya/core/context/cache/gemini.py`
- Modify: `packages/sonya-core/src/sonya/core/context/cache/__init__.py`
- Test: `packages/sonya-core/tests/test_cache_gemini.py`

**Step 1: Write failing test with mocked SDK**

```python
"""GeminiCache tests with mocked google-genai SDK."""

import pytest

from unittest.mock import AsyncMock, MagicMock, patch
from sonya.core.types import CacheConfig, CachedContent, CacheUsage
from sonya.core.context.cache.gemini import GeminiCache


@pytest.fixture
def mock_genai():
    """Mock google.genai module and its types."""
    mock_client = MagicMock()
    mock_client.aio.caches.create = AsyncMock()
    mock_client.aio.caches.get = AsyncMock()
    mock_client.aio.caches.list = AsyncMock()
    mock_client.aio.caches.update = AsyncMock()
    mock_client.aio.caches.delete = AsyncMock()

    mock_genai_module = MagicMock()
    mock_genai_module.Client.return_value = mock_client

    mock_types = MagicMock()

    return mock_genai_module, mock_types, mock_client


@pytest.fixture
def gemini_cache(mock_genai):
    mock_genai_module, mock_types, _ = mock_genai
    with patch.dict('sys.modules', {
        'google': MagicMock(),
        'google.genai': mock_genai_module,
        'google.genai.types': mock_types,
    }):
        with patch(
            'sonya.core.context.cache.gemini.genai',
            mock_genai_module,
        ):
            cache = GeminiCache.__new__(GeminiCache)
            cache._api_key = None
            cache._sdk = mock_genai_module.Client()
            cache._types = mock_types
            return cache


@pytest.mark.asyncio
async def test_create(gemini_cache, mock_genai):
    _, mock_types, mock_client = mock_genai
    _sdk_response = MagicMock()
    _sdk_response.name = 'cachedContents/abc'
    _sdk_response.model = 'gemini-2.0-flash-001'
    _sdk_response.display_name = 'Test'
    _sdk_response.create_time = '2026-03-05T00:00:00Z'
    _sdk_response.expire_time = '2026-03-05T01:00:00Z'
    _sdk_response.usage_metadata.total_token_count = 5000
    mock_client.aio.caches.create.return_value = (
        _sdk_response
    )

    config = CacheConfig(
        model='gemini-2.0-flash-001',
        display_name='Test',
        ttl='3600s',
    )
    result = await gemini_cache.create(config)

    assert isinstance(result, CachedContent)
    assert result.name == 'cachedContents/abc'
    assert result.provider == 'gemini'
    assert result.token_count == 5000


@pytest.mark.asyncio
async def test_get(gemini_cache, mock_genai):
    _, _, mock_client = mock_genai
    _sdk_response = MagicMock()
    _sdk_response.name = 'cachedContents/abc'
    _sdk_response.model = 'gemini-2.0-flash-001'
    _sdk_response.display_name = None
    _sdk_response.create_time = None
    _sdk_response.expire_time = None
    _sdk_response.usage_metadata.total_token_count = 0
    mock_client.aio.caches.get.return_value = (
        _sdk_response
    )

    result = await gemini_cache.get('cachedContents/abc')
    assert result.name == 'cachedContents/abc'


@pytest.mark.asyncio
async def test_delete(gemini_cache, mock_genai):
    _, _, mock_client = mock_genai
    mock_client.aio.caches.delete.return_value = None

    await gemini_cache.delete('cachedContents/abc')
    mock_client.aio.caches.delete.assert_called_once_with(
        name='cachedContents/abc'
    )


def test_parse_usage():
    response = MagicMock()
    response.usage_metadata.prompt_token_count = 2048
    response.usage_metadata.cached_content_token_count = (
        1024
    )

    usage = GeminiCache.parse_usage(response)
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 1024
    assert usage.total_input_tokens == 2048
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_gemini.py -v`
Expected: FAIL — `sonya.core.context.cache.gemini` not found

**Step 3: Implement GeminiCache**

Create `packages/sonya-core/src/sonya/core/context/cache/gemini.py`:

```python
"""Gemini context caching via google-genai SDK."""

from __future__ import annotations

from typing import Any

from sonya.core.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.context.cache.base import BaseCache


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
            await self._sdk.aio.caches.list()
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
```

**Step 4: Update `__init__.py` re-exports**

Modify `packages/sonya-core/src/sonya/core/context/cache/__init__.py`:

```python
"""Cache provider re-exports."""

from sonya.core.context.cache.base import BaseCache
from sonya.core.context.cache.gemini import GeminiCache

__all__ = [
    'BaseCache',
    'GeminiCache',
]
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_gemini.py -v`
Expected: All 4 tests PASS

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/cache/gemini.py packages/sonya-core/src/sonya/core/context/cache/__init__.py packages/sonya-core/tests/test_cache_gemini.py
git commit -m "feat: add GeminiCache with full CRUD support"
```

---

### Task 4: Implement AnthropicCache

**Files:**
- Create: `packages/sonya-core/src/sonya/core/context/cache/anthropic.py`
- Modify: `packages/sonya-core/src/sonya/core/context/cache/__init__.py`
- Test: `packages/sonya-core/tests/test_cache_anthropic.py`

**Step 1: Write failing test**

```python
"""AnthropicCache tests — local config storage + cache_control injection."""

import pytest

from sonya.core.types import CacheConfig, CachedContent, CacheUsage
from sonya.core.context.cache.anthropic import AnthropicCache
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
    response = MagicMock()
    response.usage.input_tokens = 500
    response.usage.cache_creation_input_tokens = 1000
    response.usage.cache_read_input_tokens = 2000

    usage = AnthropicCache.parse_usage(response)
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 2000
    assert usage.cache_creation_tokens == 1000
    assert usage.total_input_tokens == 3500
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_anthropic.py -v`
Expected: FAIL — module not found

**Step 3: Implement AnthropicCache**

Create `packages/sonya-core/src/sonya/core/context/cache/anthropic.py`:

```python
"""Anthropic prompt caching — local config + cache_control injection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sonya.core.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.context.cache.base import BaseCache


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
        _name = f'anthropic-cache-{uuid.uuid4().hex[:8]}'
        _now = datetime.now(timezone.utc).isoformat()
        _entry = _CacheEntry(config=config, name=_name)
        self._store[_name] = _entry
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
            total_input_tokens=_input + _creation + _read,
        )


class _CacheEntry:
    """Internal storage entry for a cache config."""

    __slots__ = ('config', 'name')

    def __init__(
        self, config: CacheConfig, name: str
    ) -> None:
        self.config = config
        self.name = name
```

**Step 4: Update `__init__.py`**

Modify `packages/sonya-core/src/sonya/core/context/cache/__init__.py`:

```python
"""Cache provider re-exports."""

from sonya.core.context.cache.base import BaseCache
from sonya.core.context.cache.anthropic import AnthropicCache
from sonya.core.context.cache.gemini import GeminiCache

__all__ = [
    'BaseCache',
    'AnthropicCache',
    'GeminiCache',
]
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_anthropic.py -v`
Expected: All 9 tests PASS

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/cache/anthropic.py packages/sonya-core/src/sonya/core/context/cache/__init__.py packages/sonya-core/tests/test_cache_anthropic.py
git commit -m "feat: add AnthropicCache with local config storage"
```

---

### Task 5: Implement OpenAICache

**Files:**
- Create: `packages/sonya-core/src/sonya/core/context/cache/openai.py`
- Modify: `packages/sonya-core/src/sonya/core/context/cache/__init__.py`
- Test: `packages/sonya-core/tests/test_cache_openai.py`

**Step 1: Write failing test**

```python
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
    response = MagicMock()
    response.usage.prompt_tokens = 2048
    _details = MagicMock()
    _details.cached_tokens = 1024
    response.usage.prompt_tokens_details = _details

    usage = OpenAICache.parse_usage(response)
    assert isinstance(usage, CacheUsage)
    assert usage.cached_tokens == 1024
    assert usage.total_input_tokens == 2048


def test_parse_usage_without_details():
    response = MagicMock()
    response.usage.prompt_tokens = 500
    response.usage.prompt_tokens_details = None

    usage = OpenAICache.parse_usage(response)
    assert usage.cached_tokens == 0
    assert usage.total_input_tokens == 500
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_openai.py -v`
Expected: FAIL — module not found

**Step 3: Implement OpenAICache**

Create `packages/sonya-core/src/sonya/core/context/cache/openai.py`:

```python
"""OpenAI automatic caching — usage observation only."""

from __future__ import annotations

from typing import Any

from sonya.core.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
)
from sonya.core.context.cache.base import BaseCache

_UNSUPPORTED_MSG = (
    'OpenAI does not support explicit cache management'
)


class OpenAICache(BaseCache):
    """Cache implementation for OpenAI automatic caching.

    OpenAI caching is fully automatic. CRUD operations
    are not supported. Only parse_usage() extracts cache
    hit information from responses.
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
```

**Step 4: Update `__init__.py`**

Modify `packages/sonya-core/src/sonya/core/context/cache/__init__.py`:

```python
"""Cache provider re-exports."""

from sonya.core.context.cache.base import BaseCache
from sonya.core.context.cache.anthropic import AnthropicCache
from sonya.core.context.cache.gemini import GeminiCache
from sonya.core.context.cache.openai import OpenAICache

__all__ = [
    'BaseCache',
    'AnthropicCache',
    'GeminiCache',
    'OpenAICache',
]
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/test_cache_openai.py -v`
Expected: All 7 tests PASS

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/cache/openai.py packages/sonya-core/src/sonya/core/context/cache/__init__.py packages/sonya-core/tests/test_cache_openai.py
git commit -m "feat: add OpenAICache with parse_usage support"
```

---

### Task 6: Wire up re-exports and run full test suite

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/__init__.py`
- Delete: `packages/sonya-core/src/sonya/core/context/cache/google.py` (empty placeholder)
- Remove: `packages/sonya-core/src/sonya/core/client/google.py:73-79` (_provider_create_caches method)

**Step 1: Update core `__init__.py` to re-export cache types**

Add to imports:

```python
from sonya.core.types import CacheConfig, CachedContent, CacheUsage
from sonya.core.context.cache import (
    BaseCache,
    AnthropicCache,
    GeminiCache,
    OpenAICache,
)
```

Add to `__all__`:

```python
    # Cache
    'CacheConfig',
    'CachedContent',
    'CacheUsage',
    'BaseCache',
    'AnthropicCache',
    'GeminiCache',
    'OpenAICache',
```

**Step 2: Delete the empty placeholder file**

```bash
rm packages/sonya-core/src/sonya/core/context/cache/google.py
```

**Step 3: Remove _provider_create_caches from GeminiClient**

Remove lines 73-79 from `packages/sonya-core/src/sonya/core/client/google.py` (the `_provider_create_caches` method) — this is now handled by GeminiCache.

**Step 4: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest packages/sonya-core/tests/ -v`
Expected: ALL tests PASS (existing + new cache tests)

**Step 5: Commit**

```bash
git add -A packages/sonya-core/
git commit -m "feat: wire up cache module re-exports and cleanup placeholders"
```
