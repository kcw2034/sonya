# Sonya

경량 Python LLM 클라이언트 프레임워크입니다. 공식 SDK를
thin wrapper로 감싸고 **kwargs 패스스루**와
**interceptor 기반 관측성**을 제공합니다.

## Status

- `sonya-core`: Thin wrapper 클라이언트, Tool 시스템, Agent Runtime,
  오케스트레이션이 구현되어 있습니다
- `sonya-cli`: Textual 기반 TUI 채팅 명령(`sonya chat`)을 사용할 수
  있습니다
- Planned: 안정화와 추가 런타임 기능 확장

## Repository Layout

```text
.
├── packages/
│   ├── sonya-cli/
│   │   └── src/sonya/cli/
│   │       ├── cli.py            # Cyclopts 엔트리포인트 (`sonya chat`)
│   │       ├── app.py            # Textual 앱 부트스트랩
│   │       ├── agent_manager.py  # 채팅 세션 + 클라이언트 라우팅
│   │       ├── screens/
│   │       │   └── chat.py       # 메인 채팅 화면
│   │       └── widgets/
│   │           ├── settings_panel.py
│   │           └── chat_panel.py
│   └── sonya-core/
│       └── src/sonya/core/
│           ├── types.py           # ClientConfig, Interceptor, AgentCallback
│           ├── errors.py          # AgentError, ToolError
│           ├── client/            # Provider 클라이언트 (Anthropic/OpenAI/Gemini)
│           ├── tool/              # @tool, ToolRegistry, ToolContext
│           ├── agent/             # Agent, AgentResult, AgentRuntime
│           ├── orchestration/     # Runner, SupervisorRuntime
│           └── logging/           # LoggingInterceptor, DebugCallback
├── _archive/                      # 이전 구현 아카이브
└── README.md
```

## Requirements

- Python 3.11+

## Installation

```bash
python -m venv .venv
source .venv/bin/activate

cd packages/sonya-core

# 특정 provider만 설치
pip install -e ".[anthropic]"
pip install -e ".[openai]"
pip install -e ".[gemini]"

# 전체 설치
pip install -e ".[all]"

# 개발 의존성 포함
pip install -e ".[all,dev]"
```

### CLI 패키지 설치

```bash
cd packages/sonya-cli
pip install -e .
```

로컬 editable 의존성과 함께 CLI를 실행하려면:

```bash
cd packages/sonya-cli
uv run sonya chat
```

## Quick Start

```python
import asyncio
from sonya.core import AnthropicClient, ClientConfig

async def main():
    config = ClientConfig(model="claude-sonnet-4-20250514")
    async with AnthropicClient(config) as client:
        response = await client.generate(
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(response)

asyncio.run(main())
```

## Streaming

```python
import asyncio
from sonya.core import OpenAIClient, ClientConfig

async def main():
    config = ClientConfig(model="gpt-4o")
    async with OpenAIClient(config) as client:
        async for chunk in client.generate_stream(
            messages=[{"role": "user", "content": "Describe Seoul."}],
        ):
            print(chunk, end="", flush=True)

asyncio.run(main())
```

## Interceptor

API 호출 전후에 로깅, 메트릭 수집 등 사용자 정의 로직을
주입할 수 있습니다.

```python
from sonya.core import ClientConfig, AnthropicClient

class LoggingInterceptor:
    async def before_request(self, messages, kwargs):
        print(f"→ {len(messages)} messages")
        return messages, kwargs

    async def after_response(self, response):
        print(f"← response received")
        return response

config = ClientConfig(
    model="claude-sonnet-4-20250514",
    interceptors=[LoggingInterceptor()],
)
client = AnthropicClient(config)
```

## Core Design

- **Thin Wrapper**: 공식 SDK를 감싸되 `**kwargs` 를 그대로 패스스루
- **BaseClient ABC**: `generate()` / `generate_stream()` 통일 인터페이스
- **Interceptor Protocol**: `before_request` / `after_response` 로 observability
- **SDK 네이티브 응답**: 별도 응답 모델 없이 각 SDK의 원본 응답 반환

## Development

```bash
cd packages/sonya-core
pip install -e ".[all,dev]"
pytest tests/ -v
```

## sonya-cli

`sonya-cli`는 Sonya 에이전트와 상호작용하기 위한 Textual TUI를
제공합니다.

```bash
cd packages/sonya-cli
uv run sonya chat
```

- 엔트리포인트: `sonya.cli.cli:app` (`sonya chat`)
- 핵심 모듈: `app.py`, `screens/chat.py`, `widgets/chat_panel.py`, `widgets/settings_panel.py`, `agent_manager.py`
- 런타임 설정: 시작 시 `python-dotenv`로 `.env`를 로드

## 용어 매핑

아래 매핑은 영문 문서(`README.md`)와 한국어 문서의 표현을
일관되게 유지하기 위한 기준입니다.

| English Term | Korean Term |
| --- | --- |
| Runtime | 런타임 |
| Orchestration | 오케스트레이션 |
| Handoff | 핸드오프 |
| Supervisor | 슈퍼바이저 |
| Tool | 도구 |
| Tool Registry | 도구 레지스트리 |
| Client | 클라이언트 |
| Provider | 프로바이더 |
| Callback | 콜백 |
| Interceptor | 인터셉터 |
| Observability | 관측성 |
| Streaming | 스트리밍 |
| Entrypoint | 엔트리포인트 |
| Thin Wrapper | 얇은 래퍼 |

## License

MIT
