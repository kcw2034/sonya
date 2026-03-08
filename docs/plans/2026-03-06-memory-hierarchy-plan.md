# Memory Hierarchy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** sonya-core에 MemoryType enum + MemoryEntry Protocol을 추가하고, sonya-pack에 계층별 메타데이터 서브클래스와 엔진 필터링을 구현한다.

**Architecture:** sonya-core는 Protocol 기반 인터페이스(MemoryType, MemoryEntry)만 정의. sonya-pack은 이를 import하여 EpisodicMeta/ProceduralMeta/SemanticMeta Pydantic 모델로 구현하고, BinContextEngine에 memory_type 필터링을 추가한다.

**Tech Stack:** Python 3.11+, dataclasses, Protocol, Pydantic v2, pytest

**Design doc:** `docs/plans/2026-03-06-memory-hierarchy-design.md`

---

### Task 1: sonya-core — MemoryType enum + MemoryEntry Protocol

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/schemas/memory.py`
- Test: `packages/sonya-core/tests/test_context_memory_types.py`

**Step 1: Write failing tests**

Add to `test_context_memory_types.py`:

```python
from sonya.core.schemas.memory import MemoryEntry, MemoryType


class TestMemoryType:
    """Verify MemoryType enum values."""

    def test_enum_values(self) -> None:
        assert MemoryType.EPISODIC.value == 'episodic'
        assert MemoryType.PROCEDURAL.value == 'procedural'
        assert MemoryType.SEMANTIC.value == 'semantic'

    def test_enum_count(self) -> None:
        assert len(MemoryType) == 3


class TestMemoryEntryProtocol:
    """Verify MemoryEntry Protocol compliance."""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(MemoryEntry, type)

    def test_conforming_class(self) -> None:
        class FakeEntry:
            @property
            def memory_type(self) -> MemoryType:
                return MemoryType.EPISODIC

            @property
            def content(self) -> str:
                return 'test'

            @property
            def timestamp(self) -> float:
                return 0.0

        assert isinstance(FakeEntry(), MemoryEntry)

    def test_non_conforming_class(self) -> None:
        class NotAnEntry:
            pass

        assert not isinstance(NotAnEntry(), MemoryEntry)
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_memory_types.py::TestMemoryType -v`
Expected: FAIL — `ImportError: cannot import name 'MemoryType'`

**Step 3: Implement MemoryType and MemoryEntry**

Add to `packages/sonya-core/src/sonya/core/schemas/memory.py`:

```python
from enum import Enum


class MemoryType(Enum):
    """Memory hierarchy classification.

    Attributes:
        EPISODIC: Past events, interaction timelines,
            success/failure sequences.
        PROCEDURAL: Methodologies, playbooks,
            tool routines, policy rules.
        SEMANTIC: General knowledge, facts, relationships,
            user preferences.
    """

    EPISODIC = 'episodic'
    PROCEDURAL = 'procedural'
    SEMANTIC = 'semantic'


@runtime_checkable
class MemoryEntry(Protocol):
    """Protocol for memory entries across all tiers.

    Any memory storage implementation must expose
    these properties at minimum.
    """

    @property
    def memory_type(self) -> MemoryType:
        """Memory tier classification."""
        ...

    @property
    def content(self) -> str:
        """Raw text content of the memory entry."""
        ...

    @property
    def timestamp(self) -> float:
        """Creation time as Unix epoch seconds."""
        ...
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/sonya-core && python -m pytest tests/test_context_memory_types.py -v`
Expected: All PASS

**Step 5: Update exports**

Modify `packages/sonya-core/src/sonya/core/schemas/__init__.py` — add `MemoryEntry`, `MemoryType` to imports and `__all__`.

Modify `packages/sonya-core/src/sonya/core/__init__.py` — add `MemoryEntry`, `MemoryType` to imports and `__all__`.

**Step 6: Commit**

```bash
git add packages/sonya-core/
git commit -m "feat(sonya-core): add MemoryType enum and MemoryEntry protocol"
```

---

### Task 2: sonya-pack — 의존성 추가 + 계층별 서브클래스

**Files:**
- Modify: `packages/sonya-pack/pyproject.toml`
- Modify: `packages/sonya-pack/src/sonya/pack/schemas/schema.py`
- Modify: `packages/sonya-pack/src/sonya/pack/schemas/__init__.py`
- Modify: `packages/sonya-pack/src/sonya/pack/__init__.py`
- Create: `packages/sonya-pack/tests/test_memory_schemas.py`

**Step 1: Add sonya-core dependency**

In `packages/sonya-pack/pyproject.toml`, add to `dependencies`:

```toml
dependencies = [
    "pydantic>=2.0",
    "sonya-core>=0.0.1",
]
```

**Step 2: Write failing tests**

Create `packages/sonya-pack/tests/test_memory_schemas.py`:

```python
"""Tests for memory hierarchy schemas."""

from __future__ import annotations

import pytest

from sonya.core.schemas.memory import MemoryEntry, MemoryType
from sonya.pack.schemas.schema import (
    EpisodicMeta,
    MessageMeta,
    ProceduralMeta,
    SemanticMeta,
)


class TestMessageMetaMemoryType:
    """Verify MessageMeta has memory_type field."""

    def test_default_memory_type(self) -> None:
        meta = MessageMeta(
            role='user', offset=0, length=10
        )
        assert meta.memory_type == MemoryType.EPISODIC

    def test_explicit_memory_type(self) -> None:
        meta = MessageMeta(
            role='user',
            offset=0,
            length=10,
            memory_type=MemoryType.PROCEDURAL,
        )
        assert meta.memory_type == MemoryType.PROCEDURAL


class TestEpisodicMeta:
    """Verify EpisodicMeta subclass."""

    def test_defaults(self) -> None:
        meta = EpisodicMeta(role='user', offset=0, length=5)
        assert meta.memory_type == MemoryType.EPISODIC
        assert meta.event_tag is None
        assert meta.outcome is None
        assert meta.related_session_id is None

    def test_full(self) -> None:
        meta = EpisodicMeta(
            role='assistant',
            offset=100,
            length=50,
            event_tag='login_attempt',
            outcome='success',
            related_session_id='sess-42',
        )
        assert meta.event_tag == 'login_attempt'
        assert meta.outcome == 'success'
        assert meta.related_session_id == 'sess-42'

    def test_is_message_meta(self) -> None:
        meta = EpisodicMeta(role='user', offset=0, length=5)
        assert isinstance(meta, MessageMeta)

    def test_satisfies_memory_entry(self) -> None:
        meta = EpisodicMeta(role='user', offset=0, length=5)
        assert isinstance(meta, MemoryEntry)


class TestProceduralMeta:
    """Verify ProceduralMeta subclass."""

    def test_defaults(self) -> None:
        meta = ProceduralMeta(role='system', offset=0, length=5)
        assert meta.memory_type == MemoryType.PROCEDURAL
        assert meta.workflow_name is None
        assert meta.step_order is None
        assert meta.trigger is None

    def test_full(self) -> None:
        meta = ProceduralMeta(
            role='system',
            offset=0,
            length=100,
            workflow_name='deploy_pipeline',
            step_order=3,
            trigger='on_merge',
        )
        assert meta.workflow_name == 'deploy_pipeline'
        assert meta.step_order == 3
        assert meta.trigger == 'on_merge'

    def test_satisfies_memory_entry(self) -> None:
        meta = ProceduralMeta(role='system', offset=0, length=5)
        assert isinstance(meta, MemoryEntry)


class TestSemanticMeta:
    """Verify SemanticMeta subclass."""

    def test_defaults(self) -> None:
        meta = SemanticMeta(role='system', offset=0, length=5)
        assert meta.memory_type == MemoryType.SEMANTIC
        assert meta.category is None
        assert meta.keywords == []
        assert meta.source_episode_id is None

    def test_full(self) -> None:
        meta = SemanticMeta(
            role='system',
            offset=0,
            length=200,
            category='company_policy',
            keywords=['security', 'access'],
            source_episode_id='ep-99',
        )
        assert meta.category == 'company_policy'
        assert meta.keywords == ['security', 'access']
        assert meta.source_episode_id == 'ep-99'

    def test_satisfies_memory_entry(self) -> None:
        meta = SemanticMeta(role='system', offset=0, length=5)
        assert isinstance(meta, MemoryEntry)
```

**Step 3: Run tests to verify they fail**

Run: `cd packages/sonya-pack && python -m pytest tests/test_memory_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'EpisodicMeta'`

**Step 4: Implement schema changes**

Modify `packages/sonya-pack/src/sonya/pack/schemas/schema.py`:

- Add `from sonya.core.schemas.memory import MemoryType` import
- Add `memory_type: MemoryType = Field(default=MemoryType.EPISODIC)` to `MessageMeta`
- Add `content` and `timestamp` as properties to `MessageMeta` so it satisfies `MemoryEntry` Protocol:
  - `content` property: returns empty string (actual content is in .bin file, not in meta)
  - `timestamp` property: already exists as field — Protocol satisfied
- Add `EpisodicMeta(MessageMeta)` class
- Add `ProceduralMeta(MessageMeta)` class
- Add `SemanticMeta(MessageMeta)` class

Note: `MemoryEntry` Protocol requires `content` property. Since `MessageMeta` stores only byte offsets (not actual text), `content` should return `''` — the engine resolves actual content via JIT read. If Protocol compliance for `content` is problematic, we add a `_content` field with default `''` that the engine populates during `build_context`.

**Step 5: Run tests to verify they pass**

Run: `cd packages/sonya-pack && python -m pytest tests/test_memory_schemas.py -v`
Expected: All PASS

**Step 6: Update exports**

Modify `packages/sonya-pack/src/sonya/pack/schemas/__init__.py`:
```python
from sonya.pack.schemas.schema import (
    EpisodicMeta,
    MessageMeta,
    ProceduralMeta,
    SemanticMeta,
    SessionIndex,
)
```

Modify `packages/sonya-pack/src/sonya/pack/__init__.py`:
```python
from sonya.pack.schemas.schema import (
    EpisodicMeta,
    MessageMeta,
    ProceduralMeta,
    SemanticMeta,
    SessionIndex,
)
```

**Step 7: Commit**

```bash
git add packages/sonya-pack/
git commit -m "feat(sonya-pack): add memory hierarchy meta subclasses"
```

---

### Task 3: sonya-pack — BinContextEngine memory_type 지원

**Files:**
- Modify: `packages/sonya-pack/src/sonya/pack/client/engine.py`
- Create: `packages/sonya-pack/tests/test_engine_memory.py`

**Step 1: Write failing tests**

Create `packages/sonya-pack/tests/test_engine_memory.py`:

```python
"""Tests for BinContextEngine memory_type support."""

from __future__ import annotations

import pytest

from sonya.core.schemas.memory import MemoryType
from sonya.pack.client.engine import BinContextEngine
from sonya.pack.schemas.schema import (
    EpisodicMeta,
    ProceduralMeta,
    SemanticMeta,
)


@pytest.fixture
def engine(tmp_path):
    return BinContextEngine(tmp_path)


class TestAddMessageMemoryType:
    """Verify add_message supports memory_type."""

    def test_default_episodic(self, engine) -> None:
        meta = engine.add_message('s1', 'user', 'hello')
        assert meta.memory_type == MemoryType.EPISODIC
        assert isinstance(meta, EpisodicMeta)

    def test_procedural(self, engine) -> None:
        meta = engine.add_message(
            's1', 'system', 'step 1: do X',
            memory_type=MemoryType.PROCEDURAL,
            workflow_name='deploy',
            step_order=1,
        )
        assert meta.memory_type == MemoryType.PROCEDURAL
        assert isinstance(meta, ProceduralMeta)
        assert meta.workflow_name == 'deploy'

    def test_semantic(self, engine) -> None:
        meta = engine.add_message(
            's1', 'system', 'company uses Python 3.11',
            memory_type=MemoryType.SEMANTIC,
            category='tech_stack',
            keywords=['python', 'version'],
        )
        assert meta.memory_type == MemoryType.SEMANTIC
        assert isinstance(meta, SemanticMeta)
        assert meta.keywords == ['python', 'version']


class TestBuildContextFilter:
    """Verify build_context filters by memory_type."""

    def test_filter_episodic_only(self, engine) -> None:
        engine.add_message('s1', 'user', 'event A')
        engine.add_message(
            's1', 'system', 'rule X',
            memory_type=MemoryType.PROCEDURAL,
        )
        engine.add_message('s1', 'assistant', 'event B')

        result = engine.build_context(
            's1', memory_type=MemoryType.EPISODIC
        )
        assert len(result) == 2
        assert result[0]['content'] == 'event A'
        assert result[1]['content'] == 'event B'

    def test_filter_none_returns_all(self, engine) -> None:
        engine.add_message('s1', 'user', 'msg1')
        engine.add_message(
            's1', 'system', 'proc1',
            memory_type=MemoryType.PROCEDURAL,
        )
        result = engine.build_context('s1')
        assert len(result) == 2

    def test_combined_filter_and_last_n(self, engine) -> None:
        for i in range(5):
            engine.add_message('s1', 'user', f'event {i}')
        engine.add_message(
            's1', 'system', 'knowledge',
            memory_type=MemoryType.SEMANTIC,
        )
        result = engine.build_context(
            's1',
            memory_type=MemoryType.EPISODIC,
            last_n_turns=2,
        )
        assert len(result) == 2
        assert result[0]['content'] == 'event 3'
        assert result[1]['content'] == 'event 4'


class TestMetadataPersistence:
    """Verify memory_type survives save/load cycle."""

    def test_round_trip(self, tmp_path) -> None:
        engine1 = BinContextEngine(tmp_path)
        engine1.add_message('s1', 'user', 'hello')
        engine1.add_message(
            's1', 'system', 'rule',
            memory_type=MemoryType.PROCEDURAL,
            workflow_name='onboard',
        )
        engine1.add_message(
            's1', 'system', 'fact',
            memory_type=MemoryType.SEMANTIC,
            category='hr',
        )

        # Reload from disk
        engine2 = BinContextEngine(tmp_path)
        session = engine2.get_session('s1')
        assert len(session.messages) == 3
        assert session.messages[0].memory_type == MemoryType.EPISODIC
        assert session.messages[1].memory_type == MemoryType.PROCEDURAL
        assert isinstance(session.messages[1], ProceduralMeta)
        assert session.messages[1].workflow_name == 'onboard'
        assert session.messages[2].memory_type == MemoryType.SEMANTIC
        assert isinstance(session.messages[2], SemanticMeta)
        assert session.messages[2].category == 'hr'
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/sonya-pack && python -m pytest tests/test_engine_memory.py -v`
Expected: FAIL — `TypeError: add_message() got an unexpected keyword argument 'memory_type'`

**Step 3: Implement engine changes**

Modify `packages/sonya-pack/src/sonya/pack/client/engine.py`:

1. Import `MemoryType` and subclass Metas
2. Update `add_message()` signature:
   ```python
   def add_message(
       self,
       session_id: str,
       role: str,
       text: str,
       *,
       token_count: int | None = None,
       memory_type: MemoryType = MemoryType.EPISODIC,
       **meta_kwargs,
   ) -> MessageMeta:
   ```
3. Create appropriate Meta subclass based on `memory_type`:
   ```python
   _META_CLASS = {
       MemoryType.EPISODIC: EpisodicMeta,
       MemoryType.PROCEDURAL: ProceduralMeta,
       MemoryType.SEMANTIC: SemanticMeta,
   }
   meta_cls = _META_CLASS[memory_type]
   meta = meta_cls(
       role=role,
       offset=offset,
       length=len(data),
       token_count=token_count,
       **meta_kwargs,
   )
   ```
4. Update `build_context()` signature:
   ```python
   def build_context(
       self,
       session_id: str,
       *,
       last_n_turns: int | None = None,
       memory_type: MemoryType | None = None,
   ) -> list[MessageDict]:
   ```
5. Add filtering before `last_n_turns` slicing:
   ```python
   if memory_type is not None:
       targets = [m for m in targets if m.memory_type == memory_type]
   ```
6. Update `_save_metadata()` / `_load_metadata()` to use Pydantic discriminated union for correct subclass serialization/deserialization. Use `model_dump()` with the class name stored in a `type` discriminator, or use `MessageMeta.__subclasses__()` pattern.

**Step 4: Run tests to verify they pass**

Run: `cd packages/sonya-pack && python -m pytest tests/test_engine_memory.py -v`
Expected: All PASS

**Step 5: Run all existing tests to check no regressions**

Run: `cd packages/sonya-pack && python -m pytest tests/ -v`
Run: `cd packages/sonya-core && python -m pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add packages/sonya-pack/
git commit -m "feat(sonya-pack): add memory_type support to BinContextEngine"
```

---

### Task 4: Final — 전체 검증 및 커밋

**Step 1: Run full test suite**

```bash
cd packages/sonya-core && python -m pytest tests/ -v
cd packages/sonya-pack && python -m pytest tests/ -v
```

Expected: All PASS, no regressions

**Step 2: Verify imports work end-to-end**

```bash
python -c "from sonya.core.schemas.memory import MemoryType, MemoryEntry; print('core OK')"
python -c "from sonya.pack.schemas.schema import EpisodicMeta, ProceduralMeta, SemanticMeta; print('pack OK')"
```

**Step 3: Tag milestone (optional)**

```bash
git tag -a v0.0.2-memory-hierarchy -m "feat: memory hierarchy (episodic, procedural, semantic)"
```
