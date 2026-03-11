# MemoryPipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** sonya-core의 MemoryPipeline 프로토콜에 대한 기본 구현체(DefaultMemoryPipeline)와 저장소(InMemoryStore, BridgeStore)를 sonya-pipeline에 추가한다.

**Architecture:** 단일 클래스 + 내부 메서드 분기 패턴. DefaultMemoryPipeline이 프로바이더별 normalize/reconstruct를 내부 메서드로 분기하고, 저장소는 MemoryStore 프로토콜로 추상화하여 InMemoryStore(기본)와 BridgeStore(영구)를 제공한다.

**Tech Stack:** Python 3.11+, sonya-core (NormalizedMessage, MemoryPipeline protocol), sonya-pack (BinContextEngine), pytest, pytest-asyncio

**Design doc:** `docs/plans/2026-03-11-memory-pipeline-design.md`

---

### Task 1: MemoryStore 프로토콜 추가

**Files:**
- Modify: `packages/sonya-pipeline/src/sonya/pipeline/schemas/types.py:1-70`
- Test: `packages/sonya-pipeline/tests/test_memory_store_protocol.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_store_protocol.py
"""Tests for MemoryStore protocol."""

from sonya.pipeline.schemas.types import MemoryStore


class _DummyStore:
    def save(self, session_id, messages):
        pass

    def load(self, session_id, last_n=None):
        return []

    def clear(self, session_id):
        pass


class _IncompleteStore:
    def save(self, session_id, messages):
        pass


def test_dummy_store_satisfies_protocol():
    assert isinstance(_DummyStore(), MemoryStore)


def test_incomplete_store_fails_protocol():
    assert not isinstance(_IncompleteStore(), MemoryStore)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_store_protocol.py -v`
Expected: FAIL with `ImportError: cannot import name 'MemoryStore'`

**Step 3: Write minimal implementation**

Add to `packages/sonya-pipeline/src/sonya/pipeline/schemas/types.py` after the existing imports, before `PipelineStage`:

```python
from sonya.core.schemas.memory import NormalizedMessage


# -- Memory store protocol ---------------------------------------------------

@runtime_checkable
class MemoryStore(Protocol):
    """Store and retrieve normalized messages by session.

    Args:
        session_id: Unique session identifier.
        messages: List of NormalizedMessage to save.
        last_n: Optional limit to load only the last N messages.
    """

    def save(
        self,
        session_id: str,
        messages: list[NormalizedMessage],
    ) -> None:
        """Save normalized messages to a session."""
        ...

    def load(
        self,
        session_id: str,
        last_n: int | None = None,
    ) -> list[NormalizedMessage]:
        """Load normalized messages from a session."""
        ...

    def clear(self, session_id: str) -> None:
        """Clear all messages in a session."""
        ...
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_store_protocol.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/schemas/types.py packages/sonya-pipeline/tests/test_memory_store_protocol.py
git commit -m "feat(sonya-pipeline): add MemoryStore protocol"
```

---

### Task 2: InMemoryStore 구현

**Files:**
- Create: `packages/sonya-pipeline/src/sonya/pipeline/stores/__init__.py`
- Create: `packages/sonya-pipeline/src/sonya/pipeline/stores/in_memory.py`
- Test: `packages/sonya-pipeline/tests/test_in_memory_store.py`

**Step 1: Write the failing test**

```python
# tests/test_in_memory_store.py
"""Tests for InMemoryStore."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.schemas.types import MemoryStore
from sonya.pipeline.stores.in_memory import InMemoryStore


def _msg(role: str, content: str) -> NormalizedMessage:
    return NormalizedMessage(role=role, content=content)


def test_satisfies_protocol():
    assert isinstance(InMemoryStore(), MemoryStore)


def test_save_and_load():
    store = InMemoryStore()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    store.save('s1', msgs)
    assert store.load('s1') == msgs


def test_load_empty_session():
    store = InMemoryStore()
    assert store.load('nonexistent') == []


def test_load_last_n():
    store = InMemoryStore()
    msgs = [_msg('user', f'm{i}') for i in range(5)]
    store.save('s1', msgs)
    result = store.load('s1', last_n=2)
    assert len(result) == 2
    assert result[0].content == 'm3'
    assert result[1].content == 'm4'


def test_save_appends():
    store = InMemoryStore()
    store.save('s1', [_msg('user', 'a')])
    store.save('s1', [_msg('user', 'b')])
    assert len(store.load('s1')) == 2


def test_clear():
    store = InMemoryStore()
    store.save('s1', [_msg('user', 'hello')])
    store.clear('s1')
    assert store.load('s1') == []


def test_clear_nonexistent():
    store = InMemoryStore()
    store.clear('nonexistent')  # should not raise
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_in_memory_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sonya.pipeline.stores'`

**Step 3: Write minimal implementation**

```python
# stores/__init__.py
"""sonya.pipeline.stores — Memory store implementations."""
```

```python
# stores/in_memory.py
"""sonya.pipeline.stores.in_memory — In-memory session store."""

from __future__ import annotations

from sonya.core.schemas.memory import NormalizedMessage


class InMemoryStore:
    """Dict-based in-memory session store.

    Messages persist only within the current process.
    Suitable for testing and short-lived sessions.

    Example::

        store = InMemoryStore()
        store.save('session-1', [msg1, msg2])
        loaded = store.load('session-1', last_n=5)
    """

    def __init__(self) -> None:
        self._sessions: dict[
            str, list[NormalizedMessage]
        ] = {}

    def save(
        self,
        session_id: str,
        messages: list[NormalizedMessage],
    ) -> None:
        """Append normalized messages to a session.

        Args:
            session_id: Unique session identifier.
            messages: Messages to append.
        """
        self._sessions.setdefault(
            session_id, []
        ).extend(messages)

    def load(
        self,
        session_id: str,
        last_n: int | None = None,
    ) -> list[NormalizedMessage]:
        """Load normalized messages from a session.

        Args:
            session_id: Unique session identifier.
            last_n: If set, return only the last N messages.

        Returns:
            List of NormalizedMessage (copy).
        """
        msgs = self._sessions.get(session_id, [])
        if last_n is not None:
            return list(msgs[-last_n:])
        return list(msgs)

    def clear(self, session_id: str) -> None:
        """Remove all messages for a session.

        Args:
            session_id: Unique session identifier.
        """
        self._sessions.pop(session_id, None)
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_in_memory_store.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/stores/ packages/sonya-pipeline/tests/test_in_memory_store.py
git commit -m "feat(sonya-pipeline): add InMemoryStore implementation"
```

---

### Task 3: BridgeStore 구현

**Files:**
- Create: `packages/sonya-pipeline/src/sonya/pipeline/stores/bridge_store.py`
- Test: `packages/sonya-pipeline/tests/test_bridge_store.py`

**Step 1: Write the failing test**

```python
# tests/test_bridge_store.py
"""Tests for BridgeStore."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.schemas.types import MemoryStore
from sonya.pipeline.stores.bridge_store import BridgeStore


class _FakeEngine:
    """Minimal BinContextEngine fake for testing."""

    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}

    def add_message(self, session_id, role, content):
        self._sessions.setdefault(session_id, []).append(
            {'role': role, 'content': content}
        )

    def build_context(self, session_id, *, last_n_turns=None):
        msgs = self._sessions.get(session_id, [])
        if last_n_turns is not None:
            return list(msgs[-last_n_turns:])
        return list(msgs)

    def clear_session(self, session_id):
        self._sessions.pop(session_id, None)


class _FakeBridge:
    """Minimal ContextBridge fake wrapping _FakeEngine."""

    def __init__(self):
        self._engine = _FakeEngine()

    @property
    def engine(self):
        return self._engine

    def save_messages(self, session_id, messages):
        count = 0
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if content:
                self._engine.add_message(
                    session_id, role, content
                )
                count += 1
        return count

    def load_context(self, session_id, *, last_n_turns=None):
        return self._engine.build_context(
            session_id, last_n_turns=last_n_turns
        )


def _msg(role: str, content: str) -> NormalizedMessage:
    return NormalizedMessage(role=role, content=content)


def test_satisfies_protocol():
    assert isinstance(BridgeStore(_FakeBridge()), MemoryStore)


def test_save_and_load():
    bridge = _FakeBridge()
    store = BridgeStore(bridge)
    store.save('s1', [_msg('user', 'hello'), _msg('assistant', 'hi')])
    result = store.load('s1')
    assert len(result) == 2
    assert result[0].role == 'user'
    assert result[0].content == 'hello'
    assert result[1].role == 'assistant'
    assert result[1].content == 'hi'


def test_load_empty():
    store = BridgeStore(_FakeBridge())
    assert store.load('nonexistent') == []


def test_load_last_n():
    bridge = _FakeBridge()
    store = BridgeStore(bridge)
    msgs = [_msg('user', f'm{i}') for i in range(5)]
    store.save('s1', msgs)
    result = store.load('s1', last_n=2)
    assert len(result) == 2
    assert result[0].content == 'm3'


def test_clear():
    bridge = _FakeBridge()
    store = BridgeStore(bridge)
    store.save('s1', [_msg('user', 'hello')])
    store.clear('s1')
    assert store.load('s1') == []
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_bridge_store.py -v`
Expected: FAIL with `ImportError: cannot import name 'BridgeStore'`

**Step 3: Write minimal implementation**

```python
# stores/bridge_store.py
"""sonya.pipeline.stores.bridge_store — Persistent store via ContextBridge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sonya.core.schemas.memory import NormalizedMessage

if TYPE_CHECKING:
    from sonya.pipeline.client.bridge import ContextBridge


class BridgeStore:
    """Persistent session store backed by ContextBridge.

    Delegates storage to BinContext via ContextBridge,
    providing durable session memory that survives
    process restarts.

    Note:
        First iteration stores role + content only.
        tool_calls/tool_results are not persisted.

    Args:
        bridge: ContextBridge instance to delegate to.

    Example::

        from sonya.pack import BinContextEngine
        from sonya.pipeline import ContextBridge, BridgeStore

        engine = BinContextEngine('./data')
        bridge = ContextBridge(engine)
        store = BridgeStore(bridge)
        store.save('session-1', normalized_msgs)
    """

    def __init__(self, bridge: ContextBridge) -> None:
        self._bridge = bridge

    def save(
        self,
        session_id: str,
        messages: list[NormalizedMessage],
    ) -> None:
        """Save normalized messages via ContextBridge.

        Converts NormalizedMessage to dict format
        and delegates to bridge.save_messages().

        Args:
            session_id: Unique session identifier.
            messages: Messages to save.
        """
        raw = [
            {'role': m.role, 'content': m.content}
            for m in messages
        ]
        self._bridge.save_messages(session_id, raw)

    def load(
        self,
        session_id: str,
        last_n: int | None = None,
    ) -> list[NormalizedMessage]:
        """Load messages from ContextBridge as NormalizedMessage.

        Args:
            session_id: Unique session identifier.
            last_n: If set, return only the last N messages.

        Returns:
            List of NormalizedMessage.
        """
        raw = self._bridge.load_context(
            session_id, last_n_turns=last_n,
        )
        return [
            NormalizedMessage(
                role=m.get('role', 'user'),
                content=m.get('content', ''),
            )
            for m in raw
        ]

    def clear(self, session_id: str) -> None:
        """Clear all messages for a session.

        Args:
            session_id: Unique session identifier.
        """
        self._bridge.engine.clear_session(session_id)
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_bridge_store.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/stores/bridge_store.py packages/sonya-pipeline/tests/test_bridge_store.py
git commit -m "feat(sonya-pipeline): add BridgeStore implementation"
```

---

### Task 4: DefaultMemoryPipeline — normalize 구현

**Files:**
- Create: `packages/sonya-pipeline/src/sonya/pipeline/client/memory.py`
- Test: `packages/sonya-pipeline/tests/test_memory_pipeline_normalize.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_pipeline_normalize.py
"""Tests for DefaultMemoryPipeline.normalize()."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.client.memory import DefaultMemoryPipeline


def test_normalize_openai():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
    result = pipeline.normalize(history, 'openai')
    assert len(result) == 2
    assert result[0] == NormalizedMessage(
        role='user', content='hello'
    )
    assert result[1] == NormalizedMessage(
        role='assistant', content='hi there'
    )


def test_normalize_anthropic_text_blocks():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi '},
                {'type': 'text', 'text': 'there'},
            ],
        },
    ]
    result = pipeline.normalize(history, 'anthropic')
    assert result[1].content == 'hi there'


def test_normalize_anthropic_string_content():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
    ]
    result = pipeline.normalize(history, 'anthropic')
    assert result[0].content == 'hello'


def test_normalize_gemini():
    pipeline = DefaultMemoryPipeline()
    history = [
        {
            'role': 'user',
            'parts': [{'text': 'hello'}],
        },
        {
            'role': 'model',
            'parts': [{'text': 'hi'}, {'text': ' there'}],
        },
    ]
    result = pipeline.normalize(history, 'gemini')
    assert result[0].role == 'user'
    assert result[0].content == 'hello'
    assert result[1].role == 'assistant'
    assert result[1].content == 'hi there'


def test_normalize_unknown_provider_falls_back_to_generic():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
    ]
    result = pipeline.normalize(history, 'unknown_provider')
    assert result[0].content == 'hello'


def test_normalize_preserves_system_messages():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'system', 'content': 'You are helpful.'},
        {'role': 'user', 'content': 'hello'},
    ]
    result = pipeline.normalize(history, 'openai')
    assert result[0].role == 'system'
    assert result[0].content == 'You are helpful.'


def test_normalize_empty_history():
    pipeline = DefaultMemoryPipeline()
    result = pipeline.normalize([], 'openai')
    assert result == []
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_pipeline_normalize.py -v`
Expected: FAIL with `ImportError: cannot import name 'DefaultMemoryPipeline'`

**Step 3: Write minimal implementation**

```python
# client/memory.py
"""sonya.pipeline.client.memory — DefaultMemoryPipeline implementation."""

from __future__ import annotations

from typing import Any

from sonya.core.schemas.memory import NormalizedMessage


class DefaultMemoryPipeline:
    """Default MemoryPipeline protocol implementation.

    Normalizes provider-native message histories to
    NormalizedMessage and reconstructs them back.
    Optionally persists sessions via a MemoryStore.

    First iteration supports text content only.
    tool_calls and tool_results are not yet handled.

    Args:
        store: Optional MemoryStore for session persistence.

    Example::

        from sonya.pipeline import DefaultMemoryPipeline

        pipeline = DefaultMemoryPipeline()
        normalized = pipeline.normalize(history, 'anthropic')
        reconstructed = pipeline.reconstruct(normalized, 'openai')
    """

    def __init__(
        self,
        store: Any | None = None,
    ) -> None:
        self._store = store

    # ── normalize ───────────────────────────────────────────────────────

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        """Normalize provider-native history to generic form.

        Args:
            history: Provider-native message list.
            source_provider: Provider name
                ('anthropic', 'openai', 'gemini').

        Returns:
            List of NormalizedMessage.
        """
        normalizer = {
            'anthropic': self._normalize_anthropic,
            'openai': self._normalize_openai,
            'gemini': self._normalize_gemini,
        }.get(source_provider, self._normalize_generic)

        return normalizer(history)

    def _normalize_anthropic(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize Anthropic-format messages.

        Anthropic content can be a string or a list of
        content blocks. Extracts text from type=='text' blocks.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if isinstance(content, list):
                texts = [
                    block.get('text', '')
                    for block in content
                    if block.get('type') == 'text'
                ]
                content = ''.join(texts)

            result.append(
                NormalizedMessage(role=role, content=content)
            )
        return result

    def _normalize_openai(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize OpenAI-format messages.

        OpenAI content is a plain string.
        """
        return [
            NormalizedMessage(
                role=msg.get('role', 'user'),
                content=msg.get('content', ''),
            )
            for msg in history
        ]

    def _normalize_gemini(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize Gemini-format messages.

        Gemini uses 'parts' list with 'text' fields.
        Role 'model' is mapped to 'assistant'.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            if role == 'model':
                role = 'assistant'

            parts = msg.get('parts', [])
            texts = [
                p.get('text', '')
                for p in parts
                if 'text' in p
            ]
            content = ''.join(texts)

            result.append(
                NormalizedMessage(role=role, content=content)
            )
        return result

    def _normalize_generic(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Fallback normalizer for unknown providers.

        Expects standard role + content string format.
        """
        return [
            NormalizedMessage(
                role=msg.get('role', 'user'),
                content=str(msg.get('content', '')),
            )
            for msg in history
        ]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_pipeline_normalize.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/client/memory.py packages/sonya-pipeline/tests/test_memory_pipeline_normalize.py
git commit -m "feat(sonya-pipeline): add DefaultMemoryPipeline.normalize()"
```

---

### Task 5: DefaultMemoryPipeline — reconstruct 구현

**Files:**
- Modify: `packages/sonya-pipeline/src/sonya/pipeline/client/memory.py`
- Test: `packages/sonya-pipeline/tests/test_memory_pipeline_reconstruct.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_pipeline_reconstruct.py
"""Tests for DefaultMemoryPipeline.reconstruct()."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.client.memory import DefaultMemoryPipeline


def _msg(role: str, content: str) -> NormalizedMessage:
    return NormalizedMessage(role=role, content=content)


def test_reconstruct_openai():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    result = pipeline.reconstruct(msgs, 'openai')
    assert result == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]


def test_reconstruct_anthropic():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    result = pipeline.reconstruct(msgs, 'anthropic')
    assert result[0] == {
        'role': 'user',
        'content': [{'type': 'text', 'text': 'hello'}],
    }
    assert result[1] == {
        'role': 'assistant',
        'content': [{'type': 'text', 'text': 'hi'}],
    }


def test_reconstruct_gemini():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    result = pipeline.reconstruct(msgs, 'gemini')
    assert result[0] == {
        'role': 'user',
        'parts': [{'text': 'hello'}],
    }
    assert result[1] == {
        'role': 'model',
        'parts': [{'text': 'hi'}],
    }


def test_reconstruct_gemini_system_role():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('system', 'Be helpful.')]
    result = pipeline.reconstruct(msgs, 'gemini')
    assert result[0]['role'] == 'user'


def test_reconstruct_unknown_provider():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello')]
    result = pipeline.reconstruct(msgs, 'unknown')
    assert result == [{'role': 'user', 'content': 'hello'}]


def test_reconstruct_empty():
    pipeline = DefaultMemoryPipeline()
    result = pipeline.reconstruct([], 'openai')
    assert result == []


def test_roundtrip_openai():
    pipeline = DefaultMemoryPipeline()
    original = [
        {'role': 'system', 'content': 'You are helpful.'},
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
    normalized = pipeline.normalize(original, 'openai')
    restored = pipeline.reconstruct(normalized, 'openai')
    assert restored == original


def test_roundtrip_cross_provider():
    pipeline = DefaultMemoryPipeline()
    anthropic_history = [
        {'role': 'user', 'content': 'hello'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi there'},
            ],
        },
    ]
    normalized = pipeline.normalize(
        anthropic_history, 'anthropic'
    )
    openai_history = pipeline.reconstruct(
        normalized, 'openai'
    )
    assert openai_history == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_pipeline_reconstruct.py -v`
Expected: FAIL with `AttributeError: 'DefaultMemoryPipeline' object has no attribute 'reconstruct'`

**Step 3: Write minimal implementation**

Add to `packages/sonya-pipeline/src/sonya/pipeline/client/memory.py` after the normalize methods:

```python
    # ── reconstruct ─────────────────────────────────────────────────────

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        """Reconstruct normalized messages to provider-native form.

        Args:
            messages: List of NormalizedMessage.
            target_provider: Target provider name
                ('anthropic', 'openai', 'gemini').

        Returns:
            Provider-native message list.
        """
        reconstructor = {
            'anthropic': self._reconstruct_anthropic,
            'openai': self._reconstruct_openai,
            'gemini': self._reconstruct_gemini,
        }.get(target_provider, self._reconstruct_generic)

        return reconstructor(messages)

    def _reconstruct_anthropic(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to Anthropic message format.

        Content is wrapped in a text content block list.
        """
        return [
            {
                'role': msg.role,
                'content': [
                    {'type': 'text', 'text': msg.content}
                ],
            }
            for msg in messages
        ]

    def _reconstruct_openai(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to OpenAI message format.

        Content is a plain string.
        """
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in messages
        ]

    def _reconstruct_gemini(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to Gemini message format.

        Uses parts list. Role 'assistant' mapped to 'model',
        'system' mapped to 'user'.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.role
            if role == 'assistant':
                role = 'model'
            elif role == 'system':
                role = 'user'

            result.append({
                'role': role,
                'parts': [{'text': msg.content}],
            })
        return result

    def _reconstruct_generic(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Fallback reconstructor for unknown providers."""
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in messages
        ]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_pipeline_reconstruct.py -v`
Expected: 8 passed

**Step 5: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/client/memory.py packages/sonya-pipeline/tests/test_memory_pipeline_reconstruct.py
git commit -m "feat(sonya-pipeline): add DefaultMemoryPipeline.reconstruct()"
```

---

### Task 6: DefaultMemoryPipeline — 세션 메모리 메서드

**Files:**
- Modify: `packages/sonya-pipeline/src/sonya/pipeline/client/memory.py`
- Test: `packages/sonya-pipeline/tests/test_memory_pipeline_session.py`

**Step 1: Write the failing test**

```python
# tests/test_memory_pipeline_session.py
"""Tests for DefaultMemoryPipeline session methods."""

import pytest

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.client.memory import DefaultMemoryPipeline
from sonya.pipeline.stores.in_memory import InMemoryStore


def test_save_and_load_session():
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())
    history = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]
    pipeline.save_session('s1', history, 'openai')
    result = pipeline.load_session('s1', 'openai')
    assert result == history


def test_load_session_cross_provider():
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())
    anthropic_history = [
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi'},
            ],
        },
    ]
    pipeline.save_session('s1', anthropic_history, 'anthropic')
    result = pipeline.load_session('s1', 'openai')
    assert result == [
        {'role': 'assistant', 'content': 'hi'},
    ]


def test_load_session_last_n():
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())
    history = [
        {'role': 'user', 'content': f'm{i}'}
        for i in range(5)
    ]
    pipeline.save_session('s1', history, 'openai')
    result = pipeline.load_session('s1', 'openai', last_n=2)
    assert len(result) == 2


def test_save_session_without_store_raises():
    pipeline = DefaultMemoryPipeline()
    with pytest.raises(ValueError, match='No store configured'):
        pipeline.save_session('s1', [], 'openai')


def test_load_session_without_store_raises():
    pipeline = DefaultMemoryPipeline()
    with pytest.raises(ValueError, match='No store configured'):
        pipeline.load_session('s1', 'openai')


def test_satisfies_memory_pipeline_protocol():
    from sonya.core.schemas.memory import MemoryPipeline
    assert isinstance(DefaultMemoryPipeline(), MemoryPipeline)
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_pipeline_session.py -v`
Expected: FAIL with `AttributeError: 'DefaultMemoryPipeline' object has no attribute 'save_session'`

**Step 3: Write minimal implementation**

Add to `packages/sonya-pipeline/src/sonya/pipeline/client/memory.py` after the reconstruct methods:

```python
    # ── session convenience methods ─────────────────────────────────────

    def save_session(
        self,
        session_id: str,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> None:
        """Normalize history and save to store.

        Args:
            session_id: Unique session identifier.
            history: Provider-native message list.
            source_provider: Provider name of the history.

        Raises:
            ValueError: If no store is configured.
        """
        if self._store is None:
            raise ValueError('No store configured')
        normalized = self.normalize(history, source_provider)
        self._store.save(session_id, normalized)

    def load_session(
        self,
        session_id: str,
        target_provider: str,
        last_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load from store and reconstruct for target provider.

        Args:
            session_id: Unique session identifier.
            target_provider: Provider name to reconstruct for.
            last_n: If set, load only the last N messages.

        Returns:
            Provider-native message list.

        Raises:
            ValueError: If no store is configured.
        """
        if self._store is None:
            raise ValueError('No store configured')
        normalized = self._store.load(session_id, last_n)
        return self.reconstruct(normalized, target_provider)
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_memory_pipeline_session.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/client/memory.py packages/sonya-pipeline/tests/test_memory_pipeline_session.py
git commit -m "feat(sonya-pipeline): add session save/load to DefaultMemoryPipeline"
```

---

### Task 7: 패키지 exports 업데이트

**Files:**
- Modify: `packages/sonya-pipeline/src/sonya/pipeline/__init__.py:1-36`
- Test: `packages/sonya-pipeline/tests/test_exports.py`

**Step 1: Write the failing test**

```python
# tests/test_exports.py
"""Tests for sonya.pipeline public exports."""


def test_memory_exports():
    from sonya.pipeline import (
        DefaultMemoryPipeline,
        InMemoryStore,
        BridgeStore,
    )
    assert DefaultMemoryPipeline is not None
    assert InMemoryStore is not None
    assert BridgeStore is not None


def test_memory_store_protocol_export():
    from sonya.pipeline import MemoryStore
    assert MemoryStore is not None


def test_existing_exports_preserved():
    from sonya.pipeline import (
        ContextBridge,
        Pipeline,
        TruncateStage,
        SystemPromptStage,
        FilterByRoleStage,
        MetadataInjectionStage,
        PipelineStage,
        SourceAdapter,
        Message,
    )
    assert all([
        ContextBridge, Pipeline, TruncateStage,
        SystemPromptStage, FilterByRoleStage,
        MetadataInjectionStage, PipelineStage,
        SourceAdapter, Message,
    ])
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_exports.py -v`
Expected: FAIL with `ImportError: cannot import name 'DefaultMemoryPipeline'`

**Step 3: Write minimal implementation**

Update `packages/sonya-pipeline/src/sonya/pipeline/__init__.py`:

```python
"""sonya-pipeline — sonya 패키지 간 데이터 파이프라인 통합

sonya-pack(BinContext) ↔ sonya-core(Agent) 사이의 데이터 흐름을 연결하고,
외부 데이터 소스와의 통합을 위한 파이프라인 모듈.
"""

from sonya.pipeline.client.bridge import ContextBridge
from sonya.pipeline.client.memory import DefaultMemoryPipeline
from sonya.pipeline.client.pipeline import (
    FilterByRoleStage,
    MetadataInjectionStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)
from sonya.pipeline.schemas.types import (
    MemoryStore,
    Message,
    PipelineStage,
    SourceAdapter,
)
from sonya.pipeline.stores.bridge_store import BridgeStore
from sonya.pipeline.stores.in_memory import InMemoryStore

__all__ = [
    # Bridge
    "ContextBridge",
    # Pipeline
    "Pipeline",
    # Built-in stages
    "TruncateStage",
    "SystemPromptStage",
    "FilterByRoleStage",
    "MetadataInjectionStage",
    # Memory
    "DefaultMemoryPipeline",
    "MemoryStore",
    "InMemoryStore",
    "BridgeStore",
    # Protocols
    "PipelineStage",
    "SourceAdapter",
    "Message",
]
```

**Step 4: Run test to verify it passes**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_exports.py -v`
Expected: 3 passed

**Step 5: Run all tests**

Run: `cd packages/sonya-pipeline && python -m pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add packages/sonya-pipeline/src/sonya/pipeline/__init__.py packages/sonya-pipeline/tests/test_exports.py
git commit -m "feat(sonya-pipeline): export memory pipeline classes"
```

---

### Task 8: 전체 통합 테스트 및 최종 검증

**Files:**
- Test: `packages/sonya-pipeline/tests/test_integration_memory.py`

**Step 1: Write the integration test**

```python
# tests/test_integration_memory.py
"""Integration tests for the full memory pipeline flow."""

from sonya.core.schemas.memory import MemoryPipeline, NormalizedMessage
from sonya.pipeline import (
    DefaultMemoryPipeline,
    InMemoryStore,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)


def test_protocol_compliance():
    """DefaultMemoryPipeline satisfies sonya-core MemoryPipeline."""
    pipeline = DefaultMemoryPipeline()
    assert isinstance(pipeline, MemoryPipeline)


def test_cross_provider_anthropic_to_openai():
    """Full normalize + reconstruct: Anthropic -> OpenAI."""
    pipeline = DefaultMemoryPipeline()
    anthropic_history = [
        {'role': 'user', 'content': 'Summarize this.'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'Here is the summary.'},
            ],
        },
    ]
    normalized = pipeline.normalize(
        anthropic_history, 'anthropic'
    )
    openai_history = pipeline.reconstruct(normalized, 'openai')
    assert openai_history == [
        {'role': 'user', 'content': 'Summarize this.'},
        {'role': 'assistant', 'content': 'Here is the summary.'},
    ]


def test_cross_provider_openai_to_gemini():
    """Full normalize + reconstruct: OpenAI -> Gemini."""
    pipeline = DefaultMemoryPipeline()
    openai_history = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]
    normalized = pipeline.normalize(openai_history, 'openai')
    gemini_history = pipeline.reconstruct(normalized, 'gemini')
    assert gemini_history == [
        {'role': 'user', 'parts': [{'text': 'hello'}]},
        {'role': 'model', 'parts': [{'text': 'hi'}]},
    ]


def test_session_memory_with_in_memory_store():
    """Save and load session via InMemoryStore."""
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())

    # Save Anthropic conversation
    pipeline.save_session('s1', [
        {'role': 'user', 'content': 'hello'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi there'},
            ],
        },
    ], 'anthropic')

    # Load as OpenAI format
    result = pipeline.load_session('s1', 'openai')
    assert result == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]


def test_memory_with_pipeline_stages_composition():
    """Memory pipeline + Pipeline stages used independently."""
    memory = DefaultMemoryPipeline(store=InMemoryStore())

    # Save conversation
    memory.save_session('s1', [
        {'role': 'user', 'content': f'msg{i}'}
        for i in range(10)
    ], 'openai')

    # Load and transform through Pipeline stages
    messages = memory.load_session('s1', 'openai')
    pipeline = Pipeline()
    pipeline.add_stage(
        SystemPromptStage('You are a helpful assistant.')
    )
    pipeline.add_stage(TruncateStage(max_turns=3))
    result = pipeline.run(messages)

    # System prompt + last 3 messages
    assert len(result) == 4
    assert result[0]['role'] == 'system'
    assert result[1]['content'] == 'msg7'
```

**Step 2: Run the integration test**

Run: `cd packages/sonya-pipeline && python -m pytest tests/test_integration_memory.py -v`
Expected: 5 passed

**Step 3: Run full test suite**

Run: `cd packages/sonya-pipeline && python -m pytest tests/ -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add packages/sonya-pipeline/tests/test_integration_memory.py
git commit -m "test(sonya-pipeline): add memory pipeline integration tests"
```
