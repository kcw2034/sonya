# Context Routing Design

## Overview

Implement context routing logic for agent handoffs that selects between caching (same provider) and memory pipeline (cross-provider) paths. This is part of a multi-package architecture where sonya-core provides types and routing interfaces.

## Multi-Package Architecture

```
packages/
├── sonya-core/        # Types, protocols, LLM clients, cache, router interface
├── sonya-pipeline/    # Memory transformation pipeline (normalize/reconstruct)
├── sonya-pack/        # Vector DB / binary data processing
└── sonya-agent/       # [Future] Agent runtime, orchestration, handoff
```

### Dependency Direction

```
sonya-agent → sonya-pipeline → sonya-core
                                    ↑
                              sonya-pack ─┘
```

## Routing Logic

### Condition A: Same Provider → Cache Path

When source and target agents use the same LLM provider:
- Pass native history directly (no format conversion needed)
- Apply caching mechanism to system prompt / tools prefix for token savings
- Record cache usage in ToolContext

### Condition B: Cross Provider → Memory Pipeline

When source and target agents use different LLM providers:
- Normalize source history to NormalizedMessage[] (provider-agnostic)
- Reconstruct to target provider's native format
- Record conversion metadata in ToolContext

## Components (sonya-core scope)

### 1. NormalizedMessage (context/memory/types.py)

```python
@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    role: str          # 'user'|'assistant'|'system'|'tool'
    content: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    metadata: dict[str, Any]  # agent_name, provider, etc.
```

### 2. MemoryPipeline Protocol (context/memory/types.py)

```python
@runtime_checkable
class MemoryPipeline(Protocol):
    def normalize(
        self, history: list[dict[str, Any]], source_provider: str
    ) -> list[NormalizedMessage]: ...

    def reconstruct(
        self, messages: list[NormalizedMessage], target_provider: str
    ) -> list[dict[str, Any]]: ...
```

### 3. ContextRouter (context/router.py)

```python
class ContextRouter:
    def __init__(
        self,
        cache_registry: dict[str, BaseCache] | None = None,
        pipeline: MemoryPipeline | None = None,
    ) -> None: ...

    async def route(
        self, source: Agent, target: Agent,
        history: list[dict[str, Any]],
        context: ToolContext,
    ) -> list[dict[str, Any]]: ...
```

- pipeline=None → graceful fallback to user/system filter
- cache_registry=None → skip caching, pass history as-is

### 4. Provider Detection

```python
def _detect_provider(agent: Agent) -> str:
    _map = {
        'AnthropicClient': 'anthropic',
        'OpenAIClient': 'openai',
        'GeminiClient': 'gemini',
    }
    return _map.get(type(agent.client).__name__, 'unknown')
```

### 5. Runner Integration

Replace runner.py handoff history reset with router call:

```python
# Before (existing)
history = [m for m in messages if m.get('role') in ('user', 'system')]

# After
history = await self._router.route(
    source=current_agent, target=next_agent,
    history=history, context=self._context,
)
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Unknown provider detected | Fallback: user/system only (existing behavior) |
| Pipeline conversion failure | Fallback: user/system only + warning log |
| Cache application failure | Pass history as-is (no caching) |
| No pipeline configured | Fallback: user/system only |

## Directory Structure (sonya-core additions)

```
packages/sonya-core/src/sonya/core/context/
├── __init__.py          # updated re-exports
├── router.py            # ContextRouter
├── cache/               # existing cache module
└── memory/
    ├── __init__.py
    └── types.py         # NormalizedMessage, MemoryPipeline Protocol
```

## Future: sonya-pipeline Implementation

sonya-pipeline will provide concrete MemoryPipeline:
- AnthropicNormalizer: content blocks → NormalizedMessage
- OpenAINormalizer: choices/message → NormalizedMessage
- GeminiNormalizer: candidates/parts → NormalizedMessage
- Reconstructors: NormalizedMessage → provider-native format

## Future: sonya-pack

sonya-pack will provide:
- VectorStore ABC with ChromaDB/Qdrant adapters
- Embedding interface for context vectorization
- Extensible for custom vector indexing algorithms

## Future: sonya-agent

sonya-agent will absorb:
- AgentRuntime, Runner, SupervisorRuntime from sonya-core
- Full handoff orchestration with ContextRouter integration
