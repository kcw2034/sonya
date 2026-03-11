# sonya-pipeline

`sonya-pack`과 `sonya-core` 사이의 데이터 흐름을 연결하는
파이프라인 패키지입니다. BinContext 저장소에서 메시지를 읽고,
Stage 체인으로 변환해 Agent 입력 포맷으로 전달합니다.

## 기능

- `ContextBridge`: BinContextEngine <-> Agent 메시지 브리지
- `Pipeline`: 메시지 리스트 순차 변환 엔진
- 내장 Stage: `TruncateStage`, `SystemPromptStage`,
  `FilterByRoleStage`, `MetadataInjectionStage`
- 확장 포인트: `PipelineStage`, `SourceAdapter`

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
from sonya.pack import BinContextEngine
from sonya.pipeline import (
    ContextBridge,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)

engine = BinContextEngine('./data')
bridge = ContextBridge(engine)

bridge.save_messages(
    'session-1',
    [
        {'role': 'user', 'content': '서울 날씨 알려줘'},
        {'role': 'assistant', 'content': '맑음, 8°C입니다.'},
    ],
)

messages = bridge.load_context('session-1')

pipeline = Pipeline()
pipeline.add_stage(
    SystemPromptStage(
        'You are a concise assistant.'
    )
)
pipeline.add_stage(TruncateStage(max_turns=6))

agent_input = pipeline.run(messages)
print(agent_input)
```

## 구조

```text
src/sonya/pipeline/
├── __init__.py
├── client/
│   ├── bridge.py              # ContextBridge
│   └── pipeline.py            # Pipeline + built-in stages
└── schemas/
    └── types.py               # Message / PipelineStage / SourceAdapter
```

## 테스트

현재 `tests/`에는 스캐폴드(`__init__.py`)만 포함되어 있으며,
패키지 전용 테스트 케이스는 추가 예정입니다.
