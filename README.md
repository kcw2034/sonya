# Sonya

Lightweight Python LLM agent framework. Thin wrappers around official
SDKs with an interceptor-based observability layer, a composable agent
runtime, and cross-provider memory pipeline.

## Status

| Package | Description | Status |
|---------|-------------|--------|
| `sonya-core` | LLM clients, Tool system, Agent Runtime, orchestration | ✅ |
| `sonya-cli` | Textual TUI chat interface (`sonya chat`) | ✅ |
| `sonya-pack` | BinContext append-only storage | ✅ |
| `sonya-pipeline` | Cross-provider message normalization + pipeline stages | ✅ |
| `sonya-extension` | LangChain model adapter | ✅ |

## Repository Layout

```text
packages/
├── sonya-core/
│   └── src/sonya/core/
│       ├── client/              # Provider clients (Anthropic/OpenAI/Gemini)
│       │   ├── provider/        # BaseClient, thin wrappers, interceptors
│       │   └── cache/           # Cache abstractions per provider
│       ├── models/              # Agent, AgentRuntime, Tool, Runner, Supervisor
│       ├── parsers/             # Response adapters + JSON schema parser
│       ├── schemas/             # types.py, events.py, memory.py
│       ├── utils/               # @tool decorator, DebugCallback, router
│       └── exceptions/          # AgentError, GuardrailError, ...
├── sonya-cli/
│   └── src/sonya/cli/           # Textual TUI, gateway client, auth
├── sonya-pack/
│   └── src/sonya/pack/          # BinContextEngine, SessionIndex
├── sonya-pipeline/
│   └── src/sonya/pipeline/      # DefaultMemoryPipeline, Pipeline stages,
│                                # InMemoryStore, BridgeStore
└── sonya-extension/
    └── src/sonya/extension/     # LangChainClient adapter
```

## Requirements

- Python 3.11+

## Installation

```bash
# Create and activate virtualenv
python -m venv .venv
source .venv/bin/activate

# Install sonya-core with desired provider(s)
cd packages/sonya-core
pip install -e ".[anthropic]"   # Anthropic only
pip install -e ".[openai]"      # OpenAI only
pip install -e ".[gemini]"      # Gemini only
pip install -e ".[all,dev]"     # all providers + dev tools
```

### Install CLI

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
            messages=[{'role': 'user', 'content': 'Hello!'}],
        )
        print(response)

asyncio.run(main())
```

## Feature Overview

### Streaming

`run_stream()` yields text chunks progressively, then the final
`AgentResult`.

```python
async for item in AgentRuntime(agent).run_stream(messages):
    if isinstance(item, str):
        print(item, end='', flush=True)
```

### Retry & Resilience

Configurable exponential-backoff retry on network-level errors.

```python
from sonya.core import ClientConfig, RetryConfig

config = ClientConfig(
    model='claude-sonnet-4-6',
    retry=RetryConfig(max_retries=5, base_delay=0.5),
)
```

### Guardrails

Limit tool calls and execution time per agent run.

```python
from sonya.core import Agent, GuardrailConfig

agent = Agent(
    name='safe_agent',
    client=client,
    tools=[search],
    guardrails=GuardrailConfig(max_tool_calls=10, max_tool_time=30.0),
)
```

### Structured Output

Enforce a JSON Schema response shape with auto-retry on validation failure.

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

### Human-in-the-Loop

Tools can require approval before execution.

```python
from sonya.core import tool

@tool(description='Delete a file', requires_approval=True)
async def delete_file(path: str) -> str: ...

class ApprovalCallback:
    async def on_approval_request(self, agent_name, tool_name, arguments) -> bool:
        return input(f'Allow {tool_name}? [y/N] ').lower() == 'y'
```

### Observability

Every run automatically collects token usage and timing metrics.

```python
result = await AgentRuntime(agent).run(messages)
usage = result.metadata['usage']  # UsageSummary

print(usage.total_input_tokens)
print(usage.total_output_tokens)
print(usage.llm_calls)
print(usage.total_latency_ms)
```

### Cross-Provider Memory Pipeline

Normalize and reconstruct messages — including tool calls — across providers.

```python
from sonya.pipeline import DefaultMemoryPipeline

pipeline = DefaultMemoryPipeline()
normalized = pipeline.normalize(anthropic_history, 'anthropic')
openai_messages = pipeline.reconstruct(normalized, 'openai')
```

## Interceptor

Inject custom logic before/after every LLM API call.

```python
from sonya.core import ClientConfig, AnthropicClient

class LoggingInterceptor:
    async def before_request(self, messages, kwargs):
        print(f'→ {len(messages)} messages')
        return messages, kwargs

    async def after_response(self, response):
        print('← response received')
        return response

config = ClientConfig(
    model='claude-sonnet-4-6',
    interceptors=[LoggingInterceptor()],
)
```

## Development

```bash
source .venv/bin/activate
python -m pytest --tb=short -q
```

## License

MIT
