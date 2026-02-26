# Sonya

Lightweight Python LLM client framework. It wraps official SDKs as thin wrappers to provide **kwargs passthrough** and **interceptor based observability**.

## Status

- `sonya-core`: Thin wrapper LLM client implementation complete (Anthropic, OpenAI, Gemini)
- Planned: Tool system, Agent Runtime, and multi-agent orchestration

## Repository Layout

```text
.
├── packages/
│   └── sonya-core/
│       └── src/sonya/core/
│           ├── _types.py          # Interceptor protocol, ClientConfig
│           └── client/
│               ├── _base.py       # BaseClient ABC
│               ├── anthropic.py   # Anthropic SDK wrapper
│               ├── openai.py      # OpenAI SDK wrapper
│               └── gemini.py      # Google Gemini SDK wrapper
├── _archive/                      # Archive of previous implementations
└── README.md
```

## Requirements

- Python 3.11+

## Installation

```bash
python -m venv .venv
source .venv/bin/activate

cd packages/sonya-core

# Install specific provider
pip install -e ".[anthropic]"
pip install -e ".[openai]"
pip install -e ".[gemini]"

# Install all providers
pip install -e ".[all]"

# Include development dependencies
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

You can inject logging, metrics collection, or other logic before and after API calls.

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

- **Thin Wrapper**: Wraps official SDKs while passing through `**kwargs` directly
- **BaseClient ABC**: Unified interface for `generate()` and `generate_stream()`
- **Interceptor Protocol**: Observability via `before_request` and `after_response`
- **Native SDK Responses**: Returns original responses from each SDK without custom models

## Development

```bash
cd packages/sonya-core
pip install -e ".[all,dev]"
pytest tests/ -v
```

## License

MIT
