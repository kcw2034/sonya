# sonya-core

Sonya 프레임워크의 코어 패키지입니다. 공식 LLM SDK를 thin wrapper로
감싸고 Tool 시스템, Agent Runtime, 멀티에이전트 오케스트레이션
프리미티브를 제공합니다.

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
│   ├── provider/                  # Anthropic/OpenAI/Gemini thin client
│   │   ├── base.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── google.py
│   │   └── interceptor.py         # LoggingInterceptor
│   └── cache/                     # provider cache 추상화/구현
│       ├── base.py
│       ├── anthropic.py
│       ├── openai.py
│       └── gemini.py
├── models/                        # Agent/Tool/Runner/Supervisor 모델
│   ├── agent.py
│   ├── agent_runtime.py
│   ├── tool.py
│   ├── tool_registry.py
│   ├── runner.py
│   └── supervisor.py
├── parsers/                       # provider 응답 어댑터 + schema parser
│   ├── adapter.py
│   └── schema_parser.py
├── schemas/                       # 공통 types/events/memory 스키마
│   ├── types.py
│   ├── events.py
│   └── memory.py
├── utils/                         # decorator/context/router/validation
│   ├── decorator.py
│   ├── tool_context.py
│   ├── router.py
│   ├── callback.py
│   ├── handoff.py
│   └── validation.py
└── exceptions/
    └── errors.py                  # AgentError, ToolError
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
            temperature=0.7,
        )
        print(response)


asyncio.run(main())
```

Tool + AgentRuntime 예시:

```python
import asyncio

from sonya.core import (
    Agent,
    AgentRuntime,
    ClientConfig,
    OpenAIClient,
    tool,
)


@tool(description='Add two integers')
def add(a: int, b: int) -> int:
    return a + b


async def main() -> None:
    client = OpenAIClient(
        ClientConfig(model='gpt-4o')
    )
    agent = Agent(
        name='math_agent',
        client=client,
        instructions='Use tools when needed.',
        tools=[add],
        max_iterations=5,
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'What is 7 + 5?'}]
    )
    print(result.text)
    await client.close()


asyncio.run(main())
```

## 설계 원칙

- **Thin wrapper**: 공식 SDK를 감싸되 API를 단순하게 유지
- **SDK passthrough**: `**kwargs`를 provider SDK로 직접 전달
- **Native responses**: SDK 원본 응답 객체를 그대로 반환
- **Protocol 기반 확장**: `Interceptor`, `AgentCallback`,
  `MemoryPipeline` 인터페이스로 확장 가능

## 주요 API

- **Client**: `BaseClient`, `AnthropicClient`, `OpenAIClient`,
  `GeminiClient`
- **Cache**: `BaseCache`, `AnthropicCache`, `OpenAICache`,
  `GeminiCache`, `CacheConfig`, `CacheUsage`
- **Tool**: `tool`, `Tool`, `ToolResult`, `ToolRegistry`, `ToolContext`
- **Agent**: `Agent`, `AgentResult`, `AgentRuntime`
- **Orchestration**: `Runner`, `RunnerConfig`, `RunnerCallback`,
  `SupervisorRuntime`, `SupervisorConfig`
- **Routing/Memory**: `ContextRouter`, `MemoryType`, `MemoryEntry`,
  `NormalizedMessage`
- **Logging/Error**: `LoggingInterceptor`, `DebugCallback`,
  `AgentError`, `ToolError`

## 예제

```bash
python examples/gemini_agent_demo.py
```

`examples/gemini_agent_demo.py` 포함 시나리오:

- 단일 Agent + Tool 호출
- Agent handoff 체인 (`triage -> weather_specialist`)

## 테스트

```bash
pytest tests/ -v
```

현재 테스트 범위:

- Provider client: `test_base_client.py`
- Cache: `test_cache_anthropic.py`, `test_cache_openai.py`,
  `test_cache_gemini.py`, `test_cache_base.py`, `test_cache_types.py`
- Tool: `test_tool_decorator.py`, `test_tool_schema.py`
- Runtime/Adapter: `test_agent_runtime.py`, `test_agent_adapter.py`
- Orchestration: `test_handoff.py`, `test_supervisor.py`
- Routing/Memory: `test_context_router.py`, `test_context_memory_types.py`
- Logging/Import: `test_logging.py`, `test_imports.py`
