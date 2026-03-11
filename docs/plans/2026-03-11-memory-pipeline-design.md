# MemoryPipeline 기본 구현체 설계

> Date: 2026-03-11
> Status: Approved
> Package: sonya-pipeline

## 목적

sonya-core의 `MemoryPipeline` 프로토콜에 대한 기본 구현체를 sonya-pipeline에 추가하여:

1. **크로스 프로바이더 핸드오프 지원**: Agent A(Claude) → Agent B(GPT) 핸드오프 시 메시지 히스토리 정규화/재구성
2. **세션 메모리 관리**: 정규화된 형태로 저장/로드하여 세션 간 메모리 유지

## 결정 사항

| 항목 | 결정 |
|------|------|
| 저장소 | in-memory 기본 + ContextBridge 영구 저장 선택적 제공 |
| 패키지 위치 | sonya-pipeline |
| 정규화 범위 | 1차: 텍스트만, 이후 도구 호출 지원 추가 |
| Pipeline 통합 | 독립 운영 (사용자가 직접 조합) |
| 아키텍처 | 단일 클래스 + 내부 메서드 분기 |

## 파일 구조

```
packages/sonya-pipeline/src/sonya/pipeline/
├── schemas/
│   └── types.py              # + MemoryStore 프로토콜 추가
├── client/
│   ├── bridge.py             # (기존) ContextBridge
│   ├── pipeline.py           # (기존) Pipeline + 빌트인 스테이지
│   └── memory.py             # (신규) DefaultMemoryPipeline
└── stores/                   # (신규) 저장소 구현
    ├── __init__.py
    ├── in_memory.py           # InMemoryStore
    └── bridge_store.py        # BridgeStore (ContextBridge 래핑)
```

## 클래스 관계

```
MemoryPipeline (sonya-core 프로토콜)
    ↑ implements
DefaultMemoryPipeline (sonya-pipeline)
    ├── normalize()  → _normalize_{provider}()
    ├── reconstruct() → _reconstruct_{provider}()
    └── store: MemoryStore (선택적 세션 저장)

MemoryStore (sonya-pipeline 프로토콜)
    ↑ implements
    ├── InMemoryStore (dict 기반, 프로세스 내 유지)
    └── BridgeStore (ContextBridge → BinContext 영구 저장)
```

## MemoryStore 프로토콜

```python
@runtime_checkable
class MemoryStore(Protocol):
    def save(self, session_id: str, messages: list[NormalizedMessage]) -> None: ...
    def load(self, session_id: str, last_n: int | None = None) -> list[NormalizedMessage]: ...
    def clear(self, session_id: str) -> None: ...
```

## InMemoryStore

- `dict[str, list[NormalizedMessage]]` 기반
- `save()`: `setdefault + extend`
- `load()`: `last_n` 슬라이싱 지원
- `clear()`: `pop(session_id)`

## BridgeStore

- `ContextBridge` 래핑
- `save()`: NormalizedMessage → `{'role', 'content'}` dict 변환 후 `bridge.save_messages()`
- `load()`: `bridge.load_context()` → NormalizedMessage 변환
- `clear()`: `bridge.engine.clear_session()`
- 1차 구현에서는 role + content만 저장/로드

## DefaultMemoryPipeline

### normalize (프로바이더 → NormalizedMessage)

프로바이더별 내부 메서드 분기:

- `_normalize_anthropic()`: content 리스트에서 `type=='text'` 블록의 text 결합
- `_normalize_openai()`: content 문자열 직접 사용
- `_normalize_gemini()`: parts에서 text 추출, role `model` → `assistant` 매핑
- `_normalize_generic()`: role + content(문자열) 그대로 변환 (fallback)

### reconstruct (NormalizedMessage → 타겟 프로바이더)

- `_reconstruct_anthropic()`: `{'role', 'content': [{'type': 'text', 'text': ...}]}`
- `_reconstruct_openai()`: `{'role', 'content': str}`
- `_reconstruct_gemini()`: `{'role': 'model'|role, 'parts': [{'text': ...}]}`
- `_reconstruct_generic()`: `{'role', 'content': str}`

### 세션 메모리 편의 메서드

- `save_session(session_id, history, source_provider)`: normalize → store.save
- `load_session(session_id, target_provider, last_n)`: store.load → reconstruct
- store가 None이면 AgentError 발생

## 사용 예시

### 크로스 프로바이더 핸드오프

```python
from sonya.pipeline import DefaultMemoryPipeline

pipeline = DefaultMemoryPipeline()
router = ContextRouter(pipeline=pipeline)
runner = Runner(RunnerConfig(agents=[claude_agent, gpt_agent], router=router))
result = await runner.run(messages, start_agent='analyst')
```

### 세션 메모리 (InMemoryStore)

```python
pipeline = DefaultMemoryPipeline(store=InMemoryStore())
pipeline.save_session('session-1', history, 'anthropic')
messages = pipeline.load_session('session-1', 'openai', last_n=10)
```

### 영구 세션 메모리 (BridgeStore)

```python
engine = BinContextEngine(path='./data')
bridge = ContextBridge(engine)
pipeline = DefaultMemoryPipeline(store=BridgeStore(bridge))
pipeline.save_session('session-1', history, 'anthropic')
messages = pipeline.load_session('session-1', 'gemini')
```

### Pipeline 스테이지와 조합

```python
memory = DefaultMemoryPipeline(store=InMemoryStore())
messages = memory.load_session('session-1', 'openai')

pipeline = Pipeline()
pipeline.add_stage(SystemPromptStage('You are a helpful assistant.'))
pipeline.add_stage(TruncateStage(max_turns=10))
agent_input = pipeline.run(messages)

result = await agent.run(agent_input)
memory.save_session('session-1', result.history, 'openai')
```

## 패키지 exports 추가

```python
"DefaultMemoryPipeline",
"MemoryStore",
"InMemoryStore",
"BridgeStore",
```
