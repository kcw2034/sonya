# Context Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement context routing logic in sonya-core that selects between cache path (same provider) and memory pipeline path (cross-provider) during agent handoffs.

**Architecture:** ContextRouter sits in `context/router.py`, receives source/target agents and history, detects providers, and routes accordingly. Memory types (`NormalizedMessage`, `MemoryPipeline` Protocol) live in `context/memory/types.py`. Runner integrates the router at the handoff point (line 127-132 of `runner.py`).

**Tech Stack:** Python 3.12, dataclasses, typing.Protocol, pytest + pytest-asyncio

---

### Task 1: NormalizedMessage Dataclass

**Files:**
- Create: `packages/sonya-core/src/sonya/core/context/memory/__init__.py`
- Create: `packages/sonya-core/src/sonya/core/context/memory/types.py`
- Test: `packages/sonya-core/tests/test_context_memory_types.py`

**Step 1: Write the failing test**

```python
"""Tests for context memory types."""

from __future__ import annotations

import pytest

from sonya.core.context.memory.types import NormalizedMessage


class TestNormalizedMessage:
    """Verify NormalizedMessage creation and immutability."""

    def test_creation_defaults(self) -> None:
        msg = NormalizedMessage(role='user', content='hello')
        assert msg.role == 'user'
        assert msg.content == 'hello'
        assert msg.tool_calls == []
        assert msg.tool_results == []
        assert msg.metadata == {}

    def test_creation_full(self) -> None:
        msg = NormalizedMessage(
            role='assistant',
            content='hi',
            tool_calls=[{'id': 'tc1', 'name': 'add'}],
            tool_results=[{'id': 'tc1', 'output': '3'}],
            metadata={'agent_name': 'calc', 'provider': 'openai'},
        )
        assert msg.role == 'assistant'
        assert len(msg.tool_calls) == 1
        assert msg.metadata['provider'] == 'openai'

    def test_frozen(self) -> None:
        msg = NormalizedMessage(role='user', content='hi')
        with pytest.raises(AttributeError):
            msg.role = 'system'  # type: ignore[misc]

    def test_slots(self) -> None:
        msg = NormalizedMessage(role='user', content='hi')
        assert not hasattr(msg, '__dict__')
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_memory_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sonya.core.context.memory'`

**Step 3: Write minimal implementation**

Create `packages/sonya-core/src/sonya/core/context/memory/__init__.py`:
```python
"""Memory types for cross-provider context normalization."""

from sonya.core.context.memory.types import (
    NormalizedMessage,
)

__all__ = ['NormalizedMessage']
```

Create `packages/sonya-core/src/sonya/core/context/memory/types.py`:
```python
"""Normalized message types for cross-provider context transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    """Provider-agnostic message representation.

    Args:
        role: Message role ('user', 'assistant', 'system', 'tool').
        content: Plain text content.
        tool_calls: Normalized tool call dicts.
        tool_results: Normalized tool result dicts.
        metadata: Extra metadata (agent_name, provider, etc).
    """

    role: str
    content: str
    tool_calls: list[dict[str, Any]] = field(
        default_factory=list
    )
    tool_results: list[dict[str, Any]] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_memory_types.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/memory/__init__.py \
       packages/sonya-core/src/sonya/core/context/memory/types.py \
       packages/sonya-core/tests/test_context_memory_types.py
git commit -m "feat: add NormalizedMessage dataclass for cross-provider context"
```

---

### Task 2: MemoryPipeline Protocol

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/context/memory/types.py`
- Modify: `packages/sonya-core/src/sonya/core/context/memory/__init__.py`
- Test: `packages/sonya-core/tests/test_context_memory_types.py`

**Step 1: Write the failing test**

Append to `tests/test_context_memory_types.py`:

```python
from sonya.core.context.memory.types import MemoryPipeline


class TestMemoryPipelineProtocol:
    """Verify MemoryPipeline Protocol compliance."""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(MemoryPipeline, '__protocol_attrs__') or (
            hasattr(MemoryPipeline, '_is_runtime_protocol')
        )

    def test_conforming_class_isinstance(self) -> None:
        class FakePipeline:
            def normalize(
                self,
                history: list[dict[str, Any]],
                source_provider: str,
            ) -> list[NormalizedMessage]:
                return []

            def reconstruct(
                self,
                messages: list[NormalizedMessage],
                target_provider: str,
            ) -> list[dict[str, Any]]:
                return []

        assert isinstance(FakePipeline(), MemoryPipeline)

    def test_non_conforming_class(self) -> None:
        class NotAPipeline:
            pass

        assert not isinstance(NotAPipeline(), MemoryPipeline)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_memory_types.py::TestMemoryPipelineProtocol -v`
Expected: FAIL with `ImportError: cannot import name 'MemoryPipeline'`

**Step 3: Write minimal implementation**

Append to `packages/sonya-core/src/sonya/core/context/memory/types.py`:

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class MemoryPipeline(Protocol):
    """Protocol for cross-provider message transformation.

    Implementations live in the sonya-pipeline package.
    sonya-core defines only the interface.

    Methods:
        normalize: Convert provider-native history to
            NormalizedMessage list.
        reconstruct: Convert NormalizedMessage list to
            target provider's native format.
    """

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        """Normalize provider-native history to generic form."""
        ...

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        """Reconstruct normalized messages to provider-native form."""
        ...
```

Update `packages/sonya-core/src/sonya/core/context/memory/__init__.py`:
```python
"""Memory types for cross-provider context normalization."""

from sonya.core.context.memory.types import (
    MemoryPipeline,
    NormalizedMessage,
)

__all__ = ['MemoryPipeline', 'NormalizedMessage']
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_memory_types.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/memory/types.py \
       packages/sonya-core/src/sonya/core/context/memory/__init__.py \
       packages/sonya-core/tests/test_context_memory_types.py
git commit -m "feat: add MemoryPipeline Protocol for cross-provider transformation"
```

---

### Task 3: ContextRouter — Provider Detection and Cache Path

**Files:**
- Create: `packages/sonya-core/src/sonya/core/context/router.py`
- Test: `packages/sonya-core/tests/test_context_router.py`

**Step 1: Write the failing test**

```python
"""Tests for ContextRouter."""

from __future__ import annotations

from typing import Any, AsyncIterator
from types import SimpleNamespace

import pytest

from sonya.core.agent.types import Agent
from sonya.core.client.base import BaseClient
from sonya.core.context.cache.base import BaseCache
from sonya.core.context.router import ContextRouter
from sonya.core.tool.context import ToolContext
from sonya.core.types import (
    CacheConfig,
    CachedContent,
    CacheUsage,
    ClientConfig,
)


# --- Helpers ---

class _DummyClient(BaseClient):
    """Minimal client for testing provider detection."""

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any,
    ) -> Any:
        return {}

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield {}


class _AnthropicClient(_DummyClient):
    pass


class _OpenAIClient(_DummyClient):
    pass


class _GeminiClient(_DummyClient):
    pass


def _make_agent(
    name: str, client: BaseClient,
) -> Agent:
    return Agent(name=name, client=client)


# --- Provider detection tests ---

class TestProviderDetection:
    """Verify _detect_provider works for all known clients."""

    def test_anthropic(self) -> None:
        client = _DummyClient(ClientConfig(model='test'))
        client.__class__.__name__ = 'AnthropicClient'
        agent = _make_agent('a', client)
        router = ContextRouter()
        assert router._detect_provider(agent) == 'anthropic'

    def test_openai(self) -> None:
        client = _DummyClient(ClientConfig(model='test'))
        client.__class__.__name__ = 'OpenAIClient'
        agent = _make_agent('a', client)
        router = ContextRouter()
        assert router._detect_provider(agent) == 'openai'

    def test_gemini(self) -> None:
        client = _DummyClient(ClientConfig(model='test'))
        client.__class__.__name__ = 'GeminiClient'
        agent = _make_agent('a', client)
        router = ContextRouter()
        assert router._detect_provider(agent) == 'gemini'

    def test_unknown(self) -> None:
        client = _DummyClient(ClientConfig(model='test'))
        client.__class__.__name__ = 'CustomClient'
        agent = _make_agent('a', client)
        router = ContextRouter()
        assert router._detect_provider(agent) == 'unknown'


# --- Same-provider (cache path) tests ---

class TestCachePath:
    """Verify same-provider routing passes history as-is."""

    @pytest.mark.asyncio
    async def test_same_provider_passthrough(self) -> None:
        """Same provider without cache → history unchanged."""
        client = _DummyClient(ClientConfig(model='test'))
        client.__class__.__name__ = 'AnthropicClient'
        source = _make_agent('a', client)
        target = _make_agent('b', client)

        router = ContextRouter()
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'},
        ]

        result = await router.route(
            source, target, history, ctx,
        )
        assert result == history

    @pytest.mark.asyncio
    async def test_same_provider_records_context(self) -> None:
        """Same provider records routing metadata in ToolContext."""
        client = _DummyClient(ClientConfig(model='test'))
        client.__class__.__name__ = 'OpenAIClient'
        source = _make_agent('a', client)
        target = _make_agent('b', client)

        router = ContextRouter()
        ctx = ToolContext()
        history = [{'role': 'user', 'content': 'hi'}]

        await router.route(source, target, history, ctx)
        assert ctx.get('routing_path') == 'cache'
        assert ctx.get('source_provider') == 'openai'
        assert ctx.get('target_provider') == 'openai'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sonya.core.context.router'`

**Step 3: Write minimal implementation**

Create `packages/sonya-core/src/sonya/core/context/router.py`:

```python
"""ContextRouter — selects cache or memory pipeline path on handoff."""

from __future__ import annotations

import logging
from typing import Any

from sonya.core.agent.types import Agent
from sonya.core.context.cache.base import BaseCache
from sonya.core.context.memory.types import MemoryPipeline
from sonya.core.tool.context import ToolContext

_log = logging.getLogger('sonya.router')

_PROVIDER_MAP: dict[str, str] = {
    'AnthropicClient': 'anthropic',
    'OpenAIClient': 'openai',
    'GeminiClient': 'gemini',
}


class ContextRouter:
    """Routes handoff context between agents.

    Selects between:
    - **Cache path** (same provider): pass native history directly.
    - **Memory pipeline** (cross provider): normalize → reconstruct.
    - **Fallback**: filter to user/system messages only.

    Args:
        cache_registry: Provider-name → BaseCache mapping.
        pipeline: Optional MemoryPipeline for cross-provider conversion.
    """

    def __init__(
        self,
        cache_registry: dict[str, BaseCache] | None = None,
        pipeline: MemoryPipeline | None = None,
    ) -> None:
        self._cache_registry = cache_registry or {}
        self._pipeline = pipeline

    def _detect_provider(self, agent: Agent) -> str:
        """Detect the LLM provider from the agent's client class name.

        Args:
            agent: The agent to inspect.

        Returns:
            Provider string ('anthropic', 'openai', 'gemini', 'unknown').
        """
        class_name = type(agent.client).__name__
        return _PROVIDER_MAP.get(class_name, 'unknown')

    async def route(
        self,
        source: Agent,
        target: Agent,
        history: list[dict[str, Any]],
        context: ToolContext,
    ) -> list[dict[str, Any]]:
        """Route context from source agent to target agent.

        Args:
            source: The agent handing off.
            target: The agent receiving the handoff.
            history: Conversation history from the source agent.
            context: Shared ToolContext for recording metadata.

        Returns:
            History list suitable for the target agent.
        """
        src_provider = self._detect_provider(source)
        tgt_provider = self._detect_provider(target)

        context.set('source_provider', src_provider)
        context.set('target_provider', tgt_provider)

        if src_provider == tgt_provider:
            return self._cache_path(
                history, src_provider, context,
            )

        return self._memory_path(
            history, src_provider, tgt_provider, context,
        )

    def _cache_path(
        self,
        history: list[dict[str, Any]],
        provider: str,
        context: ToolContext,
    ) -> list[dict[str, Any]]:
        """Same-provider path: pass history directly.

        Args:
            history: Native message history.
            provider: The shared provider name.
            context: ToolContext for recording metadata.

        Returns:
            The history unchanged.
        """
        context.set('routing_path', 'cache')
        _log.debug(
            'Cache path: %s (same provider)', provider,
        )
        return history

    def _memory_path(
        self,
        history: list[dict[str, Any]],
        src_provider: str,
        tgt_provider: str,
        context: ToolContext,
    ) -> list[dict[str, Any]]:
        """Cross-provider path: normalize then reconstruct.

        Falls back to user/system filter if no pipeline is configured
        or if conversion fails.

        Args:
            history: Source provider's native message history.
            src_provider: Source provider name.
            tgt_provider: Target provider name.
            context: ToolContext for recording metadata.

        Returns:
            Converted history or fallback filtered history.
        """
        context.set('routing_path', 'memory')

        if self._pipeline is None:
            _log.warning(
                'No pipeline configured; '
                'falling back to user/system filter',
            )
            context.set('routing_path', 'fallback')
            return self._fallback(history)

        try:
            normalized = self._pipeline.normalize(
                history, src_provider,
            )
            result = self._pipeline.reconstruct(
                normalized, tgt_provider,
            )
            _log.debug(
                'Memory path: %s -> %s (%d messages)',
                src_provider, tgt_provider, len(result),
            )
            return result
        except Exception:
            _log.warning(
                'Pipeline conversion failed; '
                'falling back to user/system filter',
                exc_info=True,
            )
            context.set('routing_path', 'fallback')
            return self._fallback(history)

    @staticmethod
    def _fallback(
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter history to user and system messages only.

        Args:
            history: Full message history.

        Returns:
            Filtered list with only user/system roles.
        """
        return [
            m for m in history
            if m.get('role') in ('user', 'system')
        ]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_router.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/router.py \
       packages/sonya-core/tests/test_context_router.py
git commit -m "feat: add ContextRouter with provider detection and cache path"
```

---

### Task 4: ContextRouter — Memory Pipeline Path and Fallback

**Files:**
- Modify: `packages/sonya-core/tests/test_context_router.py`
- (No production code changes needed — logic already in Task 3)

**Step 1: Write the failing test**

Append to `tests/test_context_router.py`:

```python
from sonya.core.context.memory.types import (
    MemoryPipeline,
    NormalizedMessage,
)


class _FakePipeline:
    """Pipeline that uppercases content on reconstruct."""

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        return [
            NormalizedMessage(
                role=m.get('role', 'user'),
                content=m.get('content', ''),
                metadata={'source': source_provider},
            )
            for m in history
        ]

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                'role': m.role,
                'content': m.content.upper(),
            }
            for m in messages
        ]


class _FailingPipeline:
    """Pipeline that always raises on normalize."""

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        raise RuntimeError('normalize failed')

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        return []


class TestMemoryPath:
    """Verify cross-provider routing through pipeline."""

    @pytest.mark.asyncio
    async def test_cross_provider_with_pipeline(self) -> None:
        """Different providers use memory pipeline."""
        client_a = _DummyClient(ClientConfig(model='test'))
        client_a.__class__.__name__ = 'AnthropicClient'
        client_b = _DummyClient(ClientConfig(model='test'))
        client_b.__class__.__name__ = 'OpenAIClient'
        source = _make_agent('a', client_a)
        target = _make_agent('b', client_b)

        router = ContextRouter(pipeline=_FakePipeline())
        ctx = ToolContext()
        history = [{'role': 'user', 'content': 'hello'}]

        result = await router.route(source, target, history, ctx)
        assert result == [{'role': 'user', 'content': 'HELLO'}]
        assert ctx.get('routing_path') == 'memory'

    @pytest.mark.asyncio
    async def test_cross_provider_no_pipeline_fallback(self) -> None:
        """No pipeline configured → fallback to user/system filter."""
        client_a = _DummyClient(ClientConfig(model='test'))
        client_a.__class__.__name__ = 'AnthropicClient'
        client_b = _DummyClient(ClientConfig(model='test'))
        client_b.__class__.__name__ = 'GeminiClient'
        source = _make_agent('a', client_a)
        target = _make_agent('b', client_b)

        router = ContextRouter()
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'},
            {'role': 'system', 'content': 'you are helpful'},
        ]

        result = await router.route(source, target, history, ctx)
        assert len(result) == 2
        assert all(
            m['role'] in ('user', 'system') for m in result
        )
        assert ctx.get('routing_path') == 'fallback'

    @pytest.mark.asyncio
    async def test_pipeline_error_fallback(self) -> None:
        """Pipeline error → graceful fallback."""
        client_a = _DummyClient(ClientConfig(model='test'))
        client_a.__class__.__name__ = 'AnthropicClient'
        client_b = _DummyClient(ClientConfig(model='test'))
        client_b.__class__.__name__ = 'OpenAIClient'
        source = _make_agent('a', client_a)
        target = _make_agent('b', client_b)

        router = ContextRouter(pipeline=_FailingPipeline())
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'bye'},
        ]

        result = await router.route(source, target, history, ctx)
        assert len(result) == 1
        assert result[0]['role'] == 'user'
        assert ctx.get('routing_path') == 'fallback'

    @pytest.mark.asyncio
    async def test_unknown_provider_fallback(self) -> None:
        """Unknown source or target provider → fallback."""
        client_a = _DummyClient(ClientConfig(model='test'))
        client_a.__class__.__name__ = 'CustomClient'
        client_b = _DummyClient(ClientConfig(model='test'))
        client_b.__class__.__name__ = 'AnthropicClient'
        source = _make_agent('a', client_a)
        target = _make_agent('b', client_b)

        router = ContextRouter()
        ctx = ToolContext()
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'bye'},
        ]

        result = await router.route(source, target, history, ctx)
        # unknown != anthropic → cross-provider → no pipeline → fallback
        assert len(result) == 1
        assert ctx.get('routing_path') == 'fallback'
```

**Step 2: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_router.py -v`
Expected: PASS (10 tests)

Note: These tests should pass immediately since the implementation was already completed in Task 3. This task adds thorough coverage for the memory pipeline and fallback paths.

**Step 3: Commit**

```bash
git add packages/sonya-core/tests/test_context_router.py
git commit -m "test: add memory pipeline and fallback path tests for ContextRouter"
```

---

### Task 5: Runner Integration — Wire ContextRouter

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/orchestration/runner.py:35-49,127-132`
- Modify: `packages/sonya-core/tests/test_handoff.py`

**Step 1: Write the failing test**

Append to `tests/test_handoff.py` (or modify existing handoff test if applicable):

```python
class TestRunnerWithRouter:
    """Verify Runner uses ContextRouter for handoffs."""

    @pytest.mark.asyncio
    async def test_same_provider_preserves_history(self) -> None:
        """Same-provider handoff preserves full history via router."""
        # Agent A hands off to B, both Anthropic → full history kept
        client_a = DummyClient(  # whatever the existing dummy is
            [_make_anthropic_tool('', '__handoff_to_b', 'tc1', {})],
        )
        client_a.__class__.__name__ = 'AnthropicClient'
        client_b = DummyClient(
            [_make_anthropic_text('Done')],
        )
        client_b.__class__.__name__ = 'AnthropicClient'

        agent_b = Agent(name='b', client=client_b)
        agent_a = Agent(
            name='a', client=client_a, handoffs=[agent_b],
        )

        router = ContextRouter()
        config = RunnerConfig(
            agents=[agent_a, agent_b],
            router=router,
        )
        runner = Runner(config)
        result = await runner.run(
            [{'role': 'user', 'content': 'Go'}],
        )
        assert result.agent_name == 'b'
        assert result.text == 'Done'
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-core && python -m pytest tests/test_handoff.py::TestRunnerWithRouter -v`
Expected: FAIL with `TypeError: RunnerConfig.__init__() got an unexpected keyword argument 'router'`

**Step 3: Modify RunnerConfig to accept router**

In `packages/sonya-core/src/sonya/core/orchestration/runner.py`, update `RunnerConfig`:

```python
from sonya.core.context.router import ContextRouter

@dataclass(slots=True)
class RunnerConfig:
    """Configuration for the Runner orchestrator.

    Args:
        agents: List of agents that can participate.
        max_handoffs: Maximum number of handoffs before stopping.
        callbacks: Optional lifecycle callbacks.
        context: Shared tool context across all agents.
        router: Optional ContextRouter for handoff context routing.
    """

    agents: list[Agent] = field(default_factory=list)
    max_handoffs: int = 10
    callbacks: list[RunnerCallback] = field(default_factory=list)
    context: ToolContext | None = None
    router: ContextRouter | None = None
```

**Step 4: Modify Runner.__init__ and handoff logic**

In the `Runner.__init__` method, store the router:

```python
def __init__(self, config: RunnerConfig) -> None:
    self._config = config
    self._context = config.context or ToolContext()
    self._router = config.router
    self._agent_map: dict[str, Agent] = {
        a.name: a for a in config.agents
    }
```

Replace the handoff history logic at lines 127-132:

```python
# Before (existing):
# history = [
#     m for m in messages
#     if m.get('role') in ('user', 'system')
# ]

# After:
if self._router is not None:
    history = await self._router.route(
        source=agent,
        target=self._agent_map[result.handoff_to],
        history=result.history,
        context=self._context,
    )
else:
    # Fallback: existing behavior
    history = [
        m for m in messages
        if m.get('role') in ('user', 'system')
    ]
```

**Step 5: Run test to verify it passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_handoff.py -v`
Expected: PASS (all existing + new tests)

**Step 6: Run full test suite**

Run: `cd packages/sonya-core && python -m pytest -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add packages/sonya-core/src/sonya/core/orchestration/runner.py \
       packages/sonya-core/tests/test_handoff.py
git commit -m "feat: integrate ContextRouter into Runner handoff logic"
```

---

### Task 6: Wire-Up — Re-exports and Update `__init__.py`

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/context/__init__.py`
- Modify: `packages/sonya-core/src/sonya/core/__init__.py`
- Modify: `packages/sonya-core/src/sonya/core/orchestration/__init__.py`

**Step 1: Update context/__init__.py**

```python
"""Context management modules."""

from sonya.core.context.router import ContextRouter
from sonya.core.context.memory.types import (
    MemoryPipeline,
    NormalizedMessage,
)

__all__ = [
    'ContextRouter',
    'MemoryPipeline',
    'NormalizedMessage',
]
```

**Step 2: Update core/__init__.py**

Add to the imports and `__all__` list:

```python
from sonya.core.context import (
    ContextRouter,
    MemoryPipeline,
    NormalizedMessage,
)
```

Add to `__all__`:
```python
# Context Routing
"ContextRouter",
"MemoryPipeline",
"NormalizedMessage",
```

**Step 3: Verify import test passes**

Run: `cd packages/sonya-core && python -m pytest tests/test_imports.py -v`
Expected: PASS

**Step 4: Run full suite**

Run: `cd packages/sonya-core && python -m pytest -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/context/__init__.py \
       packages/sonya-core/src/sonya/core/__init__.py
git commit -m "feat: export ContextRouter and memory types from sonya.core"
```

---

### Task 7: Verification Report

**Files:**
- Create: `docs/reports/2026-03-05-context-routing-verification.md`

**Step 1: Run full test suite and capture output**

Run: `cd packages/sonya-core && python -m pytest -v --tb=short 2>&1`

**Step 2: Write verification report**

The report must cover these criteria per the user's original requirements:

1. **Routing Accuracy**: Same-provider → cache path, cross-provider → memory/fallback path
2. **Token Leakage**: No provider-specific tokens cross provider boundaries in fallback
3. **Data Integrity**: Messages survive round-trip through pipeline without data loss
4. **Exception Safety**: Pipeline errors gracefully fallback, no unhandled exceptions

Template:

```markdown
# Context Routing Verification Report

**Date:** 2026-03-05
**Scope:** sonya-core context routing (ContextRouter, NormalizedMessage, MemoryPipeline Protocol)

## Test Results

[Paste pytest output here]

## Routing Accuracy

| Scenario | Expected Path | Actual Path | Status |
|----------|---------------|-------------|--------|
| Same provider (Anthropic→Anthropic) | cache | cache | ✅ |
| Same provider (OpenAI→OpenAI) | cache | cache | ✅ |
| Cross provider (Anthropic→OpenAI) w/ pipeline | memory | memory | ✅ |
| Cross provider no pipeline | fallback | fallback | ✅ |
| Unknown provider | fallback | fallback | ✅ |

## Token Leakage

- Fallback path filters to user/system roles only — no assistant/tool messages leak
- Pipeline path delegates conversion to MemoryPipeline (sonya-pipeline responsibility)
- Cache path passes native history — same provider, no format conflict

## Data Integrity

- NormalizedMessage is frozen+slots — immutable after creation
- FakePipeline test verifies content survives normalize→reconstruct
- Metadata preserved through routing (source_provider, target_provider recorded)

## Exception Safety

- Pipeline RuntimeError → graceful fallback to user/system filter
- No pipeline configured → graceful fallback
- All error paths set routing_path='fallback' in ToolContext
- Errors logged with exc_info=True for debugging

## Conclusion

[PASS/FAIL summary]
```

**Step 3: Commit**

```bash
git add docs/reports/2026-03-05-context-routing-verification.md
git commit -m "docs: add context routing verification report"
```
