# sonya-pack

`sonya-pack`은 BinContext 기반의 경량 컨텍스트 저장 엔진입니다.
대화 메시지를 append-only 바이너리 로그(`context.bin`)에 저장하고,
메타데이터 인덱스(`metadata.json`)로 필요한 구간만 복원합니다.

## 기능

- `offset`, `length` 포인터 기반 append-only 바이너리 저장
- 세션 단위 메시지 인덱싱 및 영속화
- `last_n_turns` 기반 최근 컨텍스트 복원
- `MemoryType`(`episodic`, `procedural`, `semantic`) 필터링
- Pydantic 기반 메타데이터 스키마 검증

## 설치

```bash
pip install -e .
```

개발 의존성 포함:

```bash
pip install -e ".[dev]"
```

## 사용법

```python
from sonya.core.schemas.memory import MemoryType
from sonya.pack import BinContextEngine

engine = BinContextEngine('./data')

engine.add_message(
    'session-1',
    'user',
    '오늘 회의를 요약해줘.',
)
engine.add_message(
    'session-1',
    'system',
    '요약은 bullet point로 작성한다.',
    memory_type=MemoryType.PROCEDURAL,
    workflow_name='meeting_summary',
    step_order=1,
)

recent = engine.build_context(
    'session-1',
    last_n_turns=5,
)
only_rules = engine.build_context(
    'session-1',
    memory_type=MemoryType.PROCEDURAL,
)

print(recent)
print(only_rules)
```

## 구조

```text
src/sonya/pack/
├── __init__.py
├── client/
│   └── engine.py              # BinContextEngine
└── schemas/
    └── schema.py              # MessageMeta / SessionIndex / memory meta
```

## 데이터 파일

엔진이 관리하는 파일:

- `context.bin`: UTF-8 메시지 원문 순차 저장
- `metadata.json`: 세션별 메시지 메타데이터 인덱스

## 예제

```bash
python examples/basic_usage.py
```

## 테스트

```bash
pytest tests/ -v
```

현재 테스트 범위:

- `test_engine_memory.py`: memory type 저장/필터/재로딩 검증
- `test_memory_schemas.py`: `EpisodicMeta`, `ProceduralMeta`,
  `SemanticMeta` 스키마 검증
