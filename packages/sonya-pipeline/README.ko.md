# sonya-pipeline

`sonya-pack`(BinContext 저장소)과 `sonya-core`(에이전트) 사이의
데이터 흐름을 연결하는 파이프라인 패키지입니다. BinContext 저장소에서
메시지를 읽고, Stage 체인으로 변환해 에이전트 입력 포맷으로 전달합니다.
크로스-프로바이더 메시지 정규화와 도구 호출/결과 영속성도 지원합니다.

## 기능

- `ContextBridge`: BinContextEngine ↔ 에이전트 메시지 브리지
  (`save_messages`, `save_agent_result`, `load_context`,
  `list_sessions`, `message_count`)
- `Pipeline`: 메시지 리스트 순차 변환 엔진
- `DefaultMemoryPipeline`: 크로스-프로바이더 정규화 및 재구성
  — **Anthropic**, **OpenAI**, **Gemini** 도구 호출/결과 지원
- `InMemoryStore`: 테스트용 인-프로세스 세션 저장소
- `BridgeStore`: BinContext 기반 영속 세션 저장소
- `FileSessionStore`: JSON 파일 기반 세션 저장소 (세션당 1파일)
- 내장 Stage: `TruncateStage`, `SystemPromptStage`,
  `FilterByRoleStage`, `MetadataInjectionStage`
- 확장 포인트: `PipelineStage`, `SourceAdapter`, `MemoryStore`

## 설치

```bash
pip install -e .
```

개발 의존성 포함:

```bash
pip install -e ".[dev]"
```

## 사용법

### Pipeline — 메시지 변환 스테이지

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
pipeline.add_stage(SystemPromptStage('You are a concise assistant.'))
pipeline.add_stage(TruncateStage(max_turns=6))

agent_input = pipeline.run(messages)
```

### DefaultMemoryPipeline — 크로스-프로바이더 정규화

프로바이더 간 메시지(도구 호출 포함)를 정규화 및 재구성합니다.

```python
from sonya.pipeline import DefaultMemoryPipeline, InMemoryStore

store = InMemoryStore()
pipeline = DefaultMemoryPipeline(store=store)

# 도구 호출이 포함된 Anthropic 히스토리
anthropic_history = [
    {
        'role': 'assistant',
        'content': [
            {'type': 'text', 'text': '검색 중...'},
            {
                'type': 'tool_use',
                'id': 'tc_1',
                'name': 'search',
                'input': {'q': '서울 날씨'},
            },
        ],
    }
]

# 정규화 후 저장
pipeline.save_session('s1', anthropic_history, 'anthropic')

# OpenAI 포맷으로 복원 — 도구 호출 보존
openai_messages = pipeline.load_session('s1', 'openai')
# openai_messages[0]['tool_calls'][0]['function']['name'] == 'search'
```

### FileSessionStore — JSON 파일 영속 저장소

```python
from sonya.pipeline.stores.file_session_store import FileSessionStore
from sonya.core import Runner, RunnerConfig

store = FileSessionStore('./sessions')   # 디렉토리 자동 생성
runner = Runner(RunnerConfig(agents=[agent], session_store=store))

result = await runner.run(
    [{'role': 'user', 'content': '안녕!'}],
    session_id='chat-001',
)
# ./sessions/chat-001.json 에 저장됨
```

각 세션 파일은 `session_id`, `history`, `agent_name`,
`metadata`, `created_at`, `updated_at`를 포함합니다.

### BridgeStore — BinContext 기반 영속 저장소

```python
from sonya.pack import BinContextEngine
from sonya.pipeline import ContextBridge, BridgeStore, DefaultMemoryPipeline

engine = BinContextEngine('./data')
bridge = ContextBridge(engine)
store = BridgeStore(bridge)

pipeline = DefaultMemoryPipeline(store=store)
pipeline.save_session('session-1', history, 'anthropic')
restored = pipeline.load_session('session-1', 'openai')
```

### ContextBridge 유틸리티

```python
bridge.save_agent_result('sess-1', agent_result)  # result.text를 저장
sessions = bridge.list_sessions()                   # 모든 세션 ID
count = bridge.message_count('sess-1')             # 메시지 수
engine = bridge.engine                             # BinContextEngine 접근
```

## 구조

```text
src/sonya/pipeline/
├── __init__.py
├── client/
│   ├── bridge.py              # ContextBridge
│   ├── memory.py              # DefaultMemoryPipeline
│   └── pipeline.py            # Pipeline + 내장 스테이지
├── schemas/
│   └── types.py               # MemoryStore / PipelineStage / SourceAdapter
└── stores/
    ├── in_memory.py           # InMemoryStore
    ├── bridge_store.py        # BridgeStore (BinContext 기반)
    └── file_session_store.py  # FileSessionStore (JSON 파일)
```

## 프로바이더 지원 매트릭스

| 프로바이더 | 텍스트 | tool_calls | tool_results |
|-----------|--------|------------|--------------|
| Anthropic | ✅ | ✅ (`tool_use` / `tool_result` 블록) | ✅ |
| OpenAI    | ✅ | ✅ (`tool_calls` 배열 / `role='tool'`) | ✅ |
| Gemini    | ✅ | ✅ (`function_call` 파트) | ✅ (`function_response` 파트) |

크로스-프로바이더 변환(예: Anthropic → OpenAI, OpenAI → Gemini) 시
도구 호출 ID와 인수가 보존됩니다. Gemini는 네이티브 호출 ID가 없어
정규화 시 합성 ID(`gemini_call_N`)가 부여됩니다.

## 테스트

```bash
pytest tests/ -v
```

현재 테스트 범위:

- `test_in_memory_store.py` — InMemoryStore 저장/로드/초기화
- `test_bridge_store.py` — BridgeStore BinContext 위임
- `test_bridge_store_tool_calls.py` — 도구 호출/결과 영속성
- `test_context_bridge_methods.py` — ContextBridge 메서드 단독 테스트
- `test_memory_store_protocol.py` — MemoryStore 프로토콜 적합성
- `test_memory_pipeline_normalize.py` — 프로바이더별 정규화
- `test_memory_pipeline_reconstruct.py` — 재구성 및 라운드트립
- `test_memory_pipeline_tool_calls.py` — 도구 호출 정규화/재구성, 크로스-프로바이더
- `test_memory_pipeline_session.py` — 저장소를 이용한 세션 저장/로드
- `test_integration_memory.py` — 엔드투엔드 흐름
- `test_pipeline_stages_isolation.py` — FilterByRoleStage, MetadataInjectionStage,
  TruncateStage, SystemPromptStage, Pipeline.stages 단독 테스트
- `test_file_session_store.py` — FileSessionStore CRUD, 라운드트립, 디렉토리 생성
- `test_exports.py` — 공개 API export
