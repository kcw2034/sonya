# Cache Module Design

## Overview

Add a unified cache abstraction layer to sonya-core that wraps the prompt caching / context caching features of Anthropic, Google Gemini, and OpenAI SDKs.

## Provider Caching Models

| Provider | Model | Management |
|----------|-------|------------|
| Anthropic | Stateless; `cache_control` block marking per-request | No server resource; local config storage |
| Gemini | Stateful `CachedContent` server resource with CRUD | Full CRUD via `client.aio.caches.*` |
| OpenAI | Fully automatic, zero-config | No management API; usage observation only |

## Architecture

Follows the same BaseClient ABC pattern used in `client/` module.

### Directory Structure

```
packages/sonya-core/src/sonya/core/
├── types.py              # CacheConfig (extended), CachedContent, CacheUsage
└── context/
    ├── __init__.py
    └── cache/
        ├── __init__.py   # re-exports
        ├── base.py       # BaseCache ABC
        ├── anthropic.py  # AnthropicCache
        ├── gemini.py     # GeminiCache
        └── openai.py     # OpenAICache
```

### Type Definitions (types.py)

```python
@dataclass(frozen=True, slots=True)
class CacheConfig:
    model: str
    display_name: str | None = None
    system_instruction: str | None = None
    contents: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    ttl: str | None = None  # e.g. '3600s', '5m', '1h'

@dataclass(frozen=True, slots=True)
class CachedContent:
    name: str
    model: str
    display_name: str | None = None
    create_time: str | None = None
    expire_time: str | None = None
    token_count: int | None = None
    provider: str = ''

@dataclass(frozen=True, slots=True)
class CacheUsage:
    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    total_input_tokens: int = 0
```

### BaseCache ABC

```python
class BaseCache(ABC):
    async def create(self, config: CacheConfig) -> CachedContent
    async def get(self, name: str) -> CachedContent
    async def list(self) -> list[CachedContent]
    async def update(self, name: str, ttl: str) -> CachedContent
    async def delete(self, name: str) -> None

    @staticmethod
    def parse_usage(response: Any) -> CacheUsage
```

### Provider Behavior

| Method | Gemini | Anthropic | OpenAI |
|--------|--------|-----------|--------|
| `create()` | `client.aio.caches.create()` | Store config locally; inject cache_control on generate | `NotImplementedError` |
| `get()` | `client.aio.caches.get()` | Return local config | `NotImplementedError` |
| `list()` | `client.aio.caches.list()` | Return local list | `NotImplementedError` |
| `update()` | `client.aio.caches.update()` | Update local TTL | `NotImplementedError` |
| `delete()` | `client.aio.caches.delete()` | Remove local entry | `NotImplementedError` |
| `parse_usage()` | Extract `cached_content_token_count` | Extract `cache_read/creation_input_tokens` | Extract `prompt_tokens_details.cached_tokens` |

## Error Handling

- Unsupported operations raise `NotImplementedError`
- SDK errors propagate as-is (thin wrapper philosophy)

## Design Decisions

1. **CacheConfig extended** from existing placeholder in types.py
2. **BaseCache ABC** mirrors BaseClient pattern for consistency
3. **Anthropic stateless→stateful mapping**: create() stores config locally, generate() auto-injects cache_control
4. **OpenAI**: only `parse_usage()` is functional; all CRUD raises NotImplementedError
