# Sonya

경량 Python LLM 클라이언트 프레임워크. 공식 SDK를 thin wrapper로 감싸서 **kwargs 패스스루**, **interceptor 기반 observability**를 제공합니다.

## Status

- `sonya-core`: Thin wrapper LLM 클라이언트 구현 완료 (Anthropic, OpenAI, Gemini)
- Planned: Tool 시스템, Agent Runtime, 멀티에이전트 오케스트레이션

## Repository Layout

```text
.
├── packages/
│   └── sonya-core/
│       └── src/sonya/core/
│           ├── _types.py          # Interceptor 프로토콜, ClientConfig
│           └── client/
│               ├── _base.py       # BaseClient ABC
│               ├── anthropic.py   # Anthropic SDK 래퍼
│               ├── openai.py      # OpenAI SDK 래퍼
│               └── gemini.py      # Google Gemini SDK 래퍼
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

API 호출 전후에 로깅, 메트릭 수집 등을 끼워넣을 수 있습니다.

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

## License

MIT
