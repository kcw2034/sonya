# Sonya

Lightweight Python LLM client framework. It wraps official SDKs as
thin wrappers and provides **kwargs passthrough** with
**interceptor-based observability**.

## Status

- `sonya-core`: Thin wrapper clients, Tool system, Agent Runtime, and
  orchestration are implemented
- `sonya-cli`: Textual-based TUI chat command (`sonya chat`) is
  available
- Planned: Further stabilization and additional runtime capabilities

## Repository Layout

```text
.
├── packages/
│   ├── sonya-cli/
│   │   └── src/sonya/cli/
│   │       ├── cli.py            # Cyclopts entrypoint (`sonya chat`)
│   │       ├── app.py            # Textual app bootstrap
│   │       ├── agent_manager.py  # Chat session + client routing
│   │       ├── screens/
│   │       │   └── chat.py       # Main chat screen
│   │       └── widgets/
│   │           ├── settings_panel.py
│   │           └── chat_panel.py
│   └── sonya-core/
│       └── src/sonya/core/
│           ├── types.py           # ClientConfig, Interceptor, AgentCallback
│           ├── errors.py          # AgentError, ToolError
│           ├── client/            # Provider clients (Anthropic/OpenAI/Gemini)
│           ├── tool/              # @tool, ToolRegistry, ToolContext
│           ├── agent/             # Agent, AgentResult, AgentRuntime
│           ├── orchestration/     # Runner, SupervisorRuntime
│           └── logging/           # LoggingInterceptor, DebugCallback
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

### Install CLI package

```bash
cd packages/sonya-cli
pip install -e .
```

Run the CLI with local editable dependencies:

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

You can inject logging, metrics collection, or custom logic before and
after API calls.

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

## sonya-cli

`sonya-cli` provides a Textual TUI for interactive chat with Sonya
agents.

For Korean terminology consistency, see `README.ko.md`.

```bash
cd packages/sonya-cli
uv run sonya chat
```

- Entrypoint: `sonya.cli.cli:app` (`sonya chat`)
- Core modules: `app.py`, `screens/chat.py`, `widgets/chat_panel.py`, `widgets/settings_panel.py`, `agent_manager.py`
- Runtime config: `.env` is loaded via `python-dotenv` on startup

## License

MIT
