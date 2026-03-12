# Sonya

경량 Python LLM 에이전트 프레임워크입니다. 공식 SDK를 thin wrapper로
감싸고 인터셉터 기반 관측성, 컴포저블 에이전트 런타임, 세션 영속성,
크로스-프로바이더 메모리 파이프라인을 제공합니다.

## Status

| 패키지 | 설명 | 상태 |
|--------|------|------|
| `sonya-core` | LLM 클라이언트, 도구 시스템, 에이전트 런타임, 오케스트레이션, 세션 영속성 | ✅ |
| `sonya-gateway` | 로컬 REST + SSE 게이트웨이 & 웹 채팅 UI (`sonya-gateway`) | ✅ |
| `sonya-cli` | Textual TUI 채팅 인터페이스 (`sonya chat`) | ✅ |
| `sonya-pack` | BinContext 추가 전용 저장소 | ✅ |
| `sonya-pipeline` | 크로스-프로바이더 메시지 정규화, 파이프라인 스테이지, FileSessionStore | ✅ |
| `sonya-extension` | LangChain 모델 어댑터 | ✅ |

## Repository Layout

```text
packages/
├── sonya-core/
│   └── src/sonya/core/
│       ├── client/              # 프로바이더 클라이언트 (Anthropic/OpenAI/Gemini)
│       │   ├── base.py          # BaseClient ABC (추상 인터페이스)
│       │   └── provider/        # AnthropicClient, OpenAIClient, GeminiClient
│       ├── cache/               # 캐시 시스템
│       │   ├── base.py          # BaseCache ABC (추상 인터페이스)
│       │   └── provider/        # AnthropicCache, OpenAICache, GeminiCache
│       ├── models/              # Agent, AgentRuntime, Tool, Runner, Supervisor,
│       │                        # Session, SessionStore
│       ├── stores/              # InMemorySessionStore
│       ├── parsers/             # 응답 어댑터 + JSON 스키마 파서
│       ├── schemas/             # types.py, events.py, memory.py
│       ├── utils/               # @tool 데코레이터, DebugCallback, ToolContext, router
│       └── exceptions/          # AgentError, GuardrailError, ...
├── sonya-cli/
│   └── src/sonya/cli/           # Textual TUI, 게이트웨이 클라이언트, 인증
├── sonya-pack/
│   └── src/sonya/pack/          # BinContextEngine, SessionIndex
├── sonya-pipeline/
│   └── src/sonya/pipeline/      # DefaultMemoryPipeline, 파이프라인 스테이지,
│                                # InMemoryStore, BridgeStore, FileSessionStore
└── sonya-extension/
    └── src/sonya/extension/     # LangChainClient 어댑터
```

## Requirements

- Python 3.11+

## 설치

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# sonya-core 설치 (원하는 프로바이더 선택)
cd packages/sonya-core
pip install -e ".[anthropic]"   # Anthropic만
pip install -e ".[openai]"      # OpenAI만
pip install -e ".[gemini]"      # Gemini만
pip install -e ".[all,dev]"     # 전체 + 개발 도구
```

### 게이트웨이 실행 (권장)

게이트웨이는 `http://localhost:8340`에서 웹 채팅 UI를 제공하며
Anthropic, OpenAI, Gemini 모델을 모두 지원합니다.

```bash
# 설치
cd packages/sonya-gateway
pip install -e "."

# API 키 설정 (하나 이상 필요)
export ANTHROPIC_API_KEY=sk-ant-...   # 또는 OPENAI_API_KEY / GOOGLE_API_KEY

# 서버 시작
sonya-gateway
# → http://localhost:8340 에서 접속
```

포트를 변경하려면 `PORT` 환경 변수를 사용합니다:

```bash
PORT=9000 sonya-gateway
```

### CLI 설치 (대안)

```bash
cd packages/sonya-cli
uv run sonya chat
```

## Quick Start

```python
import asyncio
from sonya.core import AnthropicClient, ClientConfig

async def main():
    config = ClientConfig(model='claude-sonnet-4-6')
    async with AnthropicClient(config) as client:
        response = await client.generate(
            messages=[{'role': 'user', 'content': '안녕하세요!'}],
        )
        print(response)

asyncio.run(main())
```

## 주요 기능

### 도구를 사용하는 에이전트

```python
from sonya.core import Agent, AgentRuntime, tool

@tool(description='웹 검색')
async def search(query: str) -> str:
    return f'{query} 검색 결과'

agent = Agent(
    name='assistant',
    client=client,
    tools=[search],
)
result = await AgentRuntime(agent).run(
    [{'role': 'user', 'content': '파이썬 뉴스 검색해줘'}]
)
print(result.text)
```

### ToolContext — 공유 상태 & 동적 도구 등록

도구 함수에 `context: ToolContext` 파라미터를 선언하면 런타임이
자동으로 주입합니다. 이 파라미터는 LLM 스키마에 노출되지 않습니다.

```python
from sonya.core import tool, ToolContext

@tool(description='검색 후 쿼리를 기억')
async def search(query: str, context: ToolContext) -> str:
    context.set('last_query', query)        # 공유 상태 저장
    return f'{query} 검색 결과'

@tool(description='마지막 검색 쿼리 반환')
async def get_last(context: ToolContext) -> str:
    return context.get('last_query', '없음')
```

실행 중에 새 도구를 동적으로 등록할 수도 있습니다:

```python
@tool()
async def bootstrap(context: ToolContext) -> str:
    @tool()
    async def extra_tool(x: str) -> str:
        """런타임에 등록되는 도구."""
        return x
    context.add_tool(extra_tool)
    return 'extra_tool이 이제 사용 가능합니다'
```

### 세션 영속성

프로세스 재시작 후에도 대화를 이어갈 수 있습니다.

```python
from sonya.core import Runner, RunnerConfig, InMemorySessionStore
# 디스크 저장: from sonya.pipeline.stores.file_session_store import FileSessionStore

store = InMemorySessionStore()
runner = Runner(RunnerConfig(agents=[agent], session_store=store))

# 첫 번째 턴 — session_id 자동 생성 또는 직접 지정
result = await runner.run(
    [{'role': 'user', 'content': '안녕하세요!'}],
    session_id='chat-001',
)

# 재개 — 이전 히스토리가 자동으로 앞에 추가됨
result = await runner.run(
    [{'role': 'user', 'content': '제가 뭐라고 했죠?'}],
    session_id='chat-001',
)
```

### 스트리밍

```python
async for item in AgentRuntime(agent).run_stream(messages):
    if isinstance(item, str):
        print(item, end='', flush=True)
```

### 재시도 & 복원력

```python
from sonya.core import ClientConfig, RetryConfig

config = ClientConfig(
    model='claude-sonnet-4-6',
    retry=RetryConfig(max_retries=5, base_delay=0.5),
)
```

### 가드레일

```python
from sonya.core import Agent, GuardrailConfig

agent = Agent(
    name='safe_agent',
    client=client,
    tools=[search],
    guardrails=GuardrailConfig(max_tool_calls=10, max_tool_time=30.0),
)
```

### 구조화 출력

```python
agent = Agent(
    name='extractor',
    client=client,
    output_schema={
        'type': 'object',
        'properties': {'name': {'type': 'string'}, 'age': {'type': 'integer'}},
        'required': ['name', 'age'],
    },
)
result = await AgentRuntime(agent).run(messages)
print(result.output)  # {'name': 'Alice', 'age': 30}
```

### 사람 개입 (Human-in-the-Loop)

```python
from sonya.core import tool

@tool(description='파일 삭제', requires_approval=True)
async def delete_file(path: str) -> str: ...

class ApprovalCallback:
    async def on_approval_request(self, agent_name, tool_name, arguments) -> bool:
        return input(f'{tool_name} 허용? [y/N] ').lower() == 'y'
```

### 관측성

실행 후 토큰 사용량과 타이밍 메트릭을 수집합니다. 콜백으로
LLM 호출 이벤트를 실시간 모니터링할 수 있습니다.

```python
# 실행 후 요약
result = await AgentRuntime(agent).run(messages)
usage = result.metadata['usage']
print(usage.total_input_tokens)
print(usage.total_latency_ms)

# 실시간 LLM 콜백
class MetricsCallback:
    async def on_llm_start(self, agent_name, iteration, message_count):
        print(f'[{agent_name}] iter={iteration}')

    async def on_llm_end(self, agent_name, iteration, input_tokens,
                         output_tokens, latency_ms):
        print(f'  토큰={input_tokens}+{output_tokens} {latency_ms:.0f}ms')

agent = Agent(..., callbacks=[MetricsCallback()])
```

### 크로스-프로바이더 메모리 파이프라인

프로바이더 간 메시지(도구 호출 포함)를 정규화 및 재구성합니다.

```python
from sonya.pipeline import DefaultMemoryPipeline

pipeline = DefaultMemoryPipeline()
normalized = pipeline.normalize(anthropic_history, 'anthropic')
openai_messages = pipeline.reconstruct(normalized, 'openai')
```

## 인터셉터

모든 LLM API 호출 전후에 커스텀 로직을 주입합니다.

```python
from sonya.core import LoggingInterceptor, ClientConfig, AnthropicClient

config = ClientConfig(
    model='claude-sonnet-4-6',
    interceptors=[LoggingInterceptor()],
)
```

## 개발

```bash
source .venv/bin/activate
python -m pytest --tb=short -q
```

## 용어 매핑

| English Term | Korean Term |
|---|---|
| Runtime | 런타임 |
| Orchestration | 오케스트레이션 |
| Handoff | 핸드오프 |
| Supervisor | 슈퍼바이저 |
| Tool | 도구 |
| Tool Registry | 도구 레지스트리 |
| Session | 세션 |
| Client | 클라이언트 |
| Provider | 프로바이더 |
| Callback | 콜백 |
| Interceptor | 인터셉터 |
| Observability | 관측성 |
| Streaming | 스트리밍 |
| Thin Wrapper | 얇은 래퍼 |

## License

MIT
