# Memory Hierarchy Design for sonya-pack

**Date**: 2026-03-06
**Status**: Approved

## Overview

sonya-pack에서 관리하는 메모리를 3계층(Episodic, Procedural, Semantic)으로 분류한다.
타입 정의와 Protocol은 sonya-core에, 구체적 Pydantic 모델과 엔진 로직은 sonya-pack에 둔다.

## Decisions

| 결정 사항 | 선택 |
|-----------|------|
| 저장 방식 | 단일 바이너리 파일, 메타데이터로 계층 구분 |
| 추가 메타데이터 | 계층별 서브클래스 (`EpisodicMeta`, `ProceduralMeta`, `SemanticMeta`) |
| 모델 배치 | sonya-core에 enum + Protocol, sonya-pack에 구현 |
| 설계 패턴 | Protocol 기반 (ABC 아님) — core의 Pydantic 비의존성 유지 |

## Memory Tiers

### Episodic Memory (일화적 메모리)
- 과거의 구체적 사건, 사용자 상호작용 타임라인, 성공/실패 경험 시퀀스
- 사례 기반 추론(Case-based Reasoning) 지원

### Procedural Memory (절차적 메모리)
- 작업 수행 방법론, 운영 플레이북, 도구 사용 루틴, 정책 규칙
- 자동화된 전문성으로 토큰 절약 및 반응 속도 향상

### Semantic Memory (의미론적 메모리)
- 일반 지식, 사실, 관계, 사용자 환경설정, 사내 규정
- 에피소드에서 증류(Distillation)된 범용 지식

## Architecture

### sonya-core (`schemas/memory.py`) — 추가분

```python
from enum import Enum
from typing import Protocol, runtime_checkable


class MemoryType(Enum):
    """Memory hierarchy classification."""
    EPISODIC = 'episodic'
    PROCEDURAL = 'procedural'
    SEMANTIC = 'semantic'


@runtime_checkable
class MemoryEntry(Protocol):
    """Protocol for memory entries across all tiers."""

    @property
    def memory_type(self) -> MemoryType: ...

    @property
    def content(self) -> str: ...

    @property
    def timestamp(self) -> float: ...
```

### sonya-pack (`schemas/schema.py`) — 변경분

```python
from sonya.core.schemas.memory import MemoryType


class MessageMeta(BaseModel, frozen=True):
    # ... existing fields ...
    memory_type: MemoryType = Field(default=MemoryType.EPISODIC)


class EpisodicMeta(MessageMeta):
    """Episodic memory metadata.

    Attributes:
        event_tag: Short label for the event.
        outcome: Success/failure indicator.
        related_session_id: Link to another session.
    """
    memory_type: MemoryType = Field(
        default=MemoryType.EPISODIC, frozen=True
    )
    event_tag: str | None = None
    outcome: str | None = None
    related_session_id: str | None = None


class ProceduralMeta(MessageMeta):
    """Procedural memory metadata.

    Attributes:
        workflow_name: Name of the workflow/playbook.
        step_order: Step sequence number.
        trigger: Condition that activates this procedure.
    """
    memory_type: MemoryType = Field(
        default=MemoryType.PROCEDURAL, frozen=True
    )
    workflow_name: str | None = None
    step_order: int | None = None
    trigger: str | None = None


class SemanticMeta(MessageMeta):
    """Semantic memory metadata.

    Attributes:
        category: Knowledge domain category.
        keywords: Searchable keyword tags.
        source_episode_id: Episode this was distilled from.
    """
    memory_type: MemoryType = Field(
        default=MemoryType.SEMANTIC, frozen=True
    )
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    source_episode_id: str | None = None
```

### sonya-pack (`client/engine.py`) — 변경분

`BinContextEngine`에 다음 변경:
- `add_message()`: `memory_type` 파라미터 추가, 적절한 Meta 서브클래스 생성
- `build_context()`: `memory_type` 필터 파라미터 추가 (특정 계층만 조회)
- `_save_metadata()` / `_load_metadata()`: 서브클래스 discriminator 기반 직렬화/역직렬화

### sonya-pack (`schemas/__init__.py`) — export 추가

```python
from sonya.pack.schemas.schema import (
    MessageMeta,
    EpisodicMeta,
    ProceduralMeta,
    SemanticMeta,
    SessionIndex,
)
```

### sonya-core (`schemas/__init__.py`) — export 추가

```python
from sonya.core.schemas.memory import MemoryType, MemoryEntry
```

## Backward Compatibility

- `MessageMeta.memory_type`의 기본값을 `MemoryType.EPISODIC`으로 설정하여 기존 코드 호환
- `build_context()`의 `memory_type` 필터는 `None`이면 전체 반환 (기존 동작 유지)
- 기존 메타데이터 JSON 로드 시 `memory_type` 필드 없으면 `EPISODIC`으로 폴백
