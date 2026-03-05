# sonya-core

Sonya 프레임워크의 코어 패키지입니다. 공식 LLM SDK thin wrapper를
기반으로 Tool, Agent Runtime, 멀티에이전트 오케스트레이션을
제공합니다.

## 설치

```bash
# 특정 provider
pip install -e ".[anthropic]"
pip install -e ".[openai]"
pip install -e ".[gemini]"

# 전체
pip install -e ".[all,dev]"
```

## 구조

```
src/sonya/core/
├── __init__.py          # 공개 API 내보내기
├── types.py             # ClientConfig, Interceptor, AgentCallback
├── errors.py            # AgentError, ToolError
├── client/
│   ├── base.py          # BaseClient ABC
│   ├── anthropic.py     # anthropic.AsyncAnthropic 래퍼
│   ├── openai.py        # openai.AsyncOpenAI 래퍼
│   └── gemini.py        # google.genai.Client 래퍼
├── tool/
│   ├── decorator.py     # @tool 데코레이터
│   ├── registry.py      # ToolRegistry (등록/실행)
│   ├── context.py       # ToolContext
│   ├── types.py         # Tool, ToolResult
│   ├── _schema.py       # Provider별 tool schema 변환
│   └── _validation.py   # 입력 검증
├── agent/
│   ├── runtime.py       # AgentRuntime 루프 실행
│   ├── types.py         # Agent, AgentResult
│   └── _adapter.py      # Provider 응답 어댑터
├── orchestration/
│   ├── runner.py        # Runner, RunnerConfig, RunnerCallback
│   ├── supervisor.py    # SupervisorRuntime, SupervisorConfig
│   └── _handoff.py      # handoff 헬퍼
└── logging/
    ├── interceptor.py   # LoggingInterceptor
    ├── callback.py      # DebugCallback
    └── events.py        # 구조화 이벤트 모델
```

## 사용법

```python
from sonya.core import AnthropicClient, ClientConfig

config = ClientConfig(model="claude-sonnet-4-20250514")
async with AnthropicClient(config) as client:
    # SDK kwargs 그대로 패스스루
    response = await client.generate(
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=2048,
        temperature=0.7,
    )
```

## 설계 원칙

- **Zero core dependencies**: 코어 패키지 자체는 의존성 없음
- **SDK passthrough**: `**kwargs`가 각 SDK 메서드에 그대로 전달
- **Native response**: 통합 응답 모델 없이 SDK 원본 응답 반환
- **Interceptor**: `before_request` / `after_response` 프로토콜로 관측성 제공

## 주요 API

- **Client**: `BaseClient`, `AnthropicClient`, `OpenAIClient`, `GeminiClient`
- **Tool**: `tool`, `Tool`, `ToolResult`, `ToolContext`, `ToolRegistry`
- **Agent**: `Agent`, `AgentResult`, `AgentRuntime`
- **Orchestration**: `Runner`, `RunnerConfig`, `RunnerCallback`, `SupervisorRuntime`, `SupervisorConfig`
- **Logging**: `LoggingInterceptor`, `DebugCallback`
- **Error**: `AgentError`, `ToolError`

## 예제

```bash
python examples/gemini_agent_demo.py
```

`examples/gemini_agent_demo.py`에는 다음 시나리오가 포함되어 있습니다.

- 단일 Agent + Tool 호출
- Agent handoff 체인 (triage -> specialist)

## 테스트

```bash
pytest tests/ -v
```

현재 테스트에는 클라이언트 래퍼 외에도 다음 범위가 포함됩니다.

- `test_tool_decorator.py`, `test_tool_schema.py`
- `test_agent_runtime.py`, `test_agent_adapter.py`
- `test_handoff.py`, `test_supervisor.py`
- `test_logging.py`
