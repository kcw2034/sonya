# sonya-core

Sonya 프레임워크의 코어 패키지입니다. 공식 LLM SDK를 thin wrapper로
감싸고 도구 시스템, 에이전트 런타임, 세션 영속성,
멀티에이전트 오케스트레이션을 제공합니다.

## 설치

```bash
# 특정 provider
pip install -e ".[anthropic]"
pip install -e ".[openai]"
pip install -e ".[gemini]"

# 전체 provider + 개발 의존성
pip install -e ".[all,dev]"
```

## 구조

```text
src/sonya/core/
├── __init__.py                    # 공개 API export
├── client/
│   ├── provider/                  # Anthropic/OpenAI/Gemini thin 클라이언트
│   │   ├── base.py                # BaseClient (재시도, 인터셉터 체인)
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── google.py
│   │   └── interceptor.py         # LoggingInterceptor
│   └── cache/                     # 프로바이더 캐시 추상화/구현
│       ├── base.py
│       ├── anthropic.py
│       ├── openai.py
│       └── gemini.py
├── models/                        # Agent/Tool/Runner/Supervisor/Session 모델
│   ├── agent.py                   # Agent, AgentResult
│   ├── agent_runtime.py           # AgentRuntime (run / run_stream)
│   ├── tool.py                    # Tool, ToolResult
│   ├── tool_registry.py           # ToolRegistry (register/unregister/has/clear)
│   ├── runner.py                  # Runner, RunnerConfig (session_store 지원)
│   ├── session.py                 # Session, SessionStore 프로토콜
│   ├── supervisor.py
│   └── prompt.py                  # Prompt, Example
├── stores/                        # 세션 저장소 구현체
│   └── in_memory.py               # InMemorySessionStore
├── parsers/                       # 프로바이더 응답 어댑터 + schema parser
│   ├── adapter.py
│   └── schema_parser.py           # ToolContext 파라미터 자동 제외
├── schemas/                       # 공통 types/events/memory 스키마
│   ├── types.py                   # ClientConfig, GuardrailConfig, RetryConfig,
│   │                              # UsageSummary, AgentCallback, Interceptor
│   ├── events.py
│   └── memory.py                  # NormalizedMessage, MemoryPipeline
├── utils/
│   ├── decorator.py               # @tool 데코레이터
│   ├── tool_context.py            # ToolContext (공유 상태 + add/remove_tool)
│   ├── router.py
│   ├── callback.py                # DebugCallback
│   ├── handoff.py
│   └── validation.py
└── exceptions/
    └── errors.py                  # AgentError, ToolError, GuardrailError,
                                   # MaxRetriesExceededError, ToolApprovalDeniedError
```

## 사용법

```python
import asyncio
from sonya.core import AnthropicClient, ClientConfig

async def main() -> None:
    config = ClientConfig(model='claude-sonnet-4-6')
    async with AnthropicClient(config) as client:
        response = await client.generate(
            messages=[{'role': 'user', 'content': 'Hello'}],
            max_tokens=1024,
        )
        print(response)

asyncio.run(main())
```

도구 + AgentRuntime 예시:

```python
import asyncio
from sonya.core import Agent, AgentRuntime, ClientConfig, OpenAIClient, tool

@tool(description='두 정수 합산')
def add(a: int, b: int) -> int:
    return a + b

async def main() -> None:
    client = OpenAIClient(ClientConfig(model='gpt-4o'))
    agent = Agent(
        name='math_agent',
        client=client,
        instructions='필요하면 도구를 사용하세요.',
        tools=[add],
        max_iterations=5,
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': '7 + 5는?'}]
    )
    print(result.text)
    await client.close()

asyncio.run(main())
```

## ToolContext — 공유 상태 & 동적 도구 등록

도구 함수에 `context: ToolContext` 파라미터를 선언하면 런타임이
자동으로 주입합니다. 이 파라미터는 LLM 스키마에 **노출되지 않습니다**.

```python
from sonya.core import tool, ToolContext

@tool(description='검색 후 쿼리 기억')
async def search(query: str, context: ToolContext) -> str:
    context.set('last_query', query)
    return f'{query} 결과'

@tool(description='마지막 검색 반환')
async def recall(context: ToolContext) -> str:
    return context.get('last_query', '없음')
```

실행 중 새 도구 동적 등록:

```python
@tool()
async def bootstrap(context: ToolContext) -> str:
    @tool()
    async def dynamic(x: str) -> str:
        """런타임 등록 도구."""
        return x
    context.add_tool(dynamic)   # 다음 LLM 이터레이션부터 사용 가능
    return '동적 도구 등록 완료'
```

## 세션 영속성

프로세스 재시작 후에도 대화를 이어갈 수 있습니다.

```python
from sonya.core import Runner, RunnerConfig, InMemorySessionStore
# 디스크 저장: from sonya.pipeline.stores.file_session_store import FileSessionStore

store = InMemorySessionStore()
runner = Runner(RunnerConfig(agents=[agent], session_store=store))

# 첫 번째 턴
result = await runner.run(
    [{'role': 'user', 'content': '안녕!'}],
    session_id='chat-001',
)

# 재개 — 이전 히스토리 자동 추가
result = await runner.run(
    [{'role': 'user', 'content': '내가 뭐라 했지?'}],
    session_id='chat-001',
)
print(result.metadata['session_id'])  # 'chat-001'
```

## 스트리밍

```python
from sonya.core import Agent, AgentRuntime, AgentResult

async for item in AgentRuntime(agent).run_stream(messages):
    if isinstance(item, str):
        print(item, end='', flush=True)
    elif isinstance(item, AgentResult):
        result = item
```

## 재시도 & 복원력

```python
from sonya.core import ClientConfig, RetryConfig, AnthropicClient

config = ClientConfig(
    model='claude-sonnet-4-6',
    retry=RetryConfig(max_retries=5, base_delay=0.5, backoff_factor=2.0),
)
```

## 가드레일

```python
from sonya.core import Agent, GuardrailConfig

agent = Agent(
    name='safe_agent',
    client=client,
    tools=[search, fetch],
    guardrails=GuardrailConfig(
        max_tool_calls=10,
        max_tool_time=30.0,         # 초
        max_concurrent_tools=3,
    ),
)
```

## 구조화 출력

```python
from sonya.core import Agent, AgentRuntime

schema = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'age': {'type': 'integer'},
    },
    'required': ['name', 'age'],
}

agent = Agent(name='extractor', client=client, output_schema=schema)
result = await AgentRuntime(agent).run(messages)
print(result.output)  # {'name': 'Alice', 'age': 30}
```

## 관측성

실행 후 토큰 사용량 및 타이밍 메트릭. `on_llm_start` / `on_llm_end`
콜백으로 LLM 호출을 실시간 모니터링할 수 있습니다.

```python
# 실행 후 집계
result = await AgentRuntime(agent).run(messages)
usage = result.metadata['usage']

print(usage.total_input_tokens)
print(usage.total_output_tokens)
print(usage.llm_calls)
print(usage.total_latency_ms)

# 실시간 LLM 콜백
class MyCallback:
    async def on_llm_start(
        self, agent_name: str, iteration: int, message_count: int
    ) -> None:
        print(f'LLM 호출 #{iteration}, 메시지 수: {message_count}')

    async def on_llm_end(
        self, agent_name: str, iteration: int,
        input_tokens: int, output_tokens: int, latency_ms: float,
    ) -> None:
        print(f'  → {input_tokens}+{output_tokens} 토큰, {latency_ms:.0f}ms')
```

## 동적 도구 레지스트리

`ToolRegistry`는 런타임 도구 관리를 지원합니다:

```python
from sonya.core import ToolRegistry

registry = ToolRegistry()
registry.register(my_tool)
registry.register_many([tool_a, tool_b])
registry.has('my_tool')       # True
registry.unregister('my_tool')
registry.clear()
```

## 주요 API

- **Client**: `BaseClient`, `AnthropicClient`, `OpenAIClient`, `GeminiClient`
- **Config**: `ClientConfig`, `RetryConfig`
- **Cache**: `BaseCache`, `AnthropicCache`, `OpenAICache`, `GeminiCache`,
  `CacheConfig`, `CacheUsage`
- **Tool**: `tool`, `Tool`, `ToolResult`, `ToolRegistry`, `ToolContext`
- **Agent**: `Agent`, `AgentResult`, `AgentRuntime`
- **Guardrails**: `GuardrailConfig`, `GuardrailError`
- **관측성**: `UsageSummary`, `AgentCallback.on_llm_start/on_llm_end`
- **Session**: `Session`, `SessionStore`, `InMemorySessionStore`
- **Orchestration**: `Runner`, `RunnerConfig`, `RunnerCallback`,
  `SupervisorRuntime`, `SupervisorConfig`
- **Routing/Memory**: `ContextRouter`, `MemoryType`, `MemoryEntry`,
  `NormalizedMessage`
- **Logging/Error**: `LoggingInterceptor`, `DebugCallback`,
  `AgentError`, `ToolError`, `GuardrailError`

## 설계 원칙

- **Thin wrapper**: 공식 SDK를 감싸되 API를 단순하게 유지
- **SDK passthrough**: `**kwargs`를 provider SDK로 직접 전달
- **Native responses**: SDK 원본 응답 객체를 그대로 반환
- **Protocol 기반 확장**: `Interceptor`, `AgentCallback`,
  `MemoryPipeline` 인터페이스로 확장 가능

## 테스트

```bash
pytest tests/ -v
```

현재 테스트 범위 (531개 테스트):

- Provider client: `test_base_client.py`, `test_base_client_retry.py`
- Cache: `test_cache_anthropic.py`, `test_cache_openai.py`,
  `test_cache_gemini.py`, `test_cache_base.py`, `test_cache_types.py`
- Tool: `test_tool_decorator.py`, `test_tool_schema.py`
- Runtime/Adapter: `test_agent_runtime.py`, `test_agent_runtime_stream.py`,
  `test_agent_adapter.py`
- 가드레일: `test_guardrails.py`
- 구조화 출력: `test_structured_output.py`
- Human-in-the-Loop: `test_human_in_the_loop.py`
- 관측성: `test_observability.py`, `test_llm_callbacks.py`
- ToolContext 주입: `test_tool_context_injection.py`
- 동적 도구: `test_dynamic_tool_registry.py`, `test_dynamic_tool_context.py`
- 세션: `test_session.py`, `test_session_runner.py`
- 병렬 도구 실행: `test_parallel_tool_execution.py`
- Orchestration: `test_handoff.py`, `test_supervisor.py`
- Routing/Memory: `test_context_router.py`, `test_context_memory_types.py`
- Export/Import: `test_top_level_exports.py`, `test_logging.py`,
  `test_imports.py`
