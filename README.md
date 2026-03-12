# Sonya

Lightweight Python LLM agent framework. Thin wrappers around official
SDKs with an interceptor-based observability layer, a composable agent
runtime, session persistence, and cross-provider memory pipeline.

## Status

| Package | Description | Status |
|---------|-------------|--------|
| `sonya-core` | LLM clients, Tool system, Agent Runtime, orchestration, session persistence | ✅ |
| `sonya-gateway` | Local REST + SSE gateway with web chat UI (`sonya-gateway`) | ✅ |
| `sonya-cli` | Textual TUI chat interface (`sonya chat`) | ✅ |
| `sonya-pack` | BinContext append-only storage | ✅ |
| `sonya-pipeline` | Cross-provider message normalization, pipeline stages, FileSessionStore | ✅ |
| `sonya-extension` | LangChain model adapter | ✅ |

## Repository Layout

```text
packages/
├── sonya-core/
│   └── src/sonya/core/
│       ├── client/              # Provider clients (Anthropic/OpenAI/Gemini)
│       │   └── provider/        # BaseClient, thin wrappers, interceptors
│       ├── cache/               # Cache system
│       │   ├── base.py          # BaseCache ABC
│       │   └── provider/        # AnthropicCache, OpenAICache, GeminiCache
│       ├── models/              # Agent, AgentRuntime, Tool, Runner, Supervisor,
│       │                        # Session, SessionStore
│       ├── stores/              # InMemorySessionStore
│       ├── parsers/             # Response adapters + JSON schema parser
│       ├── schemas/             # types.py, events.py, memory.py
│       ├── utils/               # @tool decorator, DebugCallback, ToolContext, router
│       └── exceptions/          # AgentError, GuardrailError, ...
├── sonya-cli/
│   └── src/sonya/cli/           # Textual TUI, gateway client, auth
├── sonya-pack/
│   └── src/sonya/pack/          # BinContextEngine, SessionIndex
├── sonya-pipeline/
│   └── src/sonya/pipeline/      # DefaultMemoryPipeline, Pipeline stages,
│                                # InMemoryStore, BridgeStore, FileSessionStore
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

### Start the Gateway (Recommended)

The gateway provides a web chat UI at `http://localhost:8340` supporting
Anthropic, OpenAI, and Gemini models.

```bash
# Install
cd packages/sonya-gateway
pip install -e "."

# Set at least one API key
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY / GOOGLE_API_KEY

# Start the server
sonya-gateway
# → open http://localhost:8340
```

Use the `PORT` environment variable to change the port:

```bash
PORT=9000 sonya-gateway
```

### Install CLI (Alternative)

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

### Agent with Tools

```python
from sonya.core import Agent, AgentRuntime, tool

@tool(description='Search the web')
async def search(query: str) -> str:
    return f'Results for: {query}'

agent = Agent(
    name='assistant',
    client=client,
    tools=[search],
)
result = await AgentRuntime(agent).run(
    [{'role': 'user', 'content': 'Search Python news'}]
)
print(result.text)
```

### ToolContext — shared state & dynamic registration

Tools can declare a `context: ToolContext` parameter to access run-scoped
shared state. This parameter is injected automatically and never exposed
to the LLM.

```python
from sonya.core import tool, ToolContext

@tool(description='Search and remember the query')
async def search(query: str, context: ToolContext) -> str:
    context.set('last_query', query)        # store shared state
    return f'Results for: {query}'

@tool(description='Get the last search query')
async def get_last(context: ToolContext) -> str:
    return context.get('last_query', 'none')
```

Tools can also register new tools dynamically mid-run:

```python
@tool()
async def bootstrap(context: ToolContext) -> str:
    @tool()
    async def extra_tool(x: str) -> str:
        """Registered at runtime."""
        return x
    context.add_tool(extra_tool)
    return 'extra_tool is now available'
```

### Session Persistence

Resume conversations across process restarts.

```python
from sonya.core import Runner, RunnerConfig, InMemorySessionStore
# or: from sonya.pipeline.stores.file_session_store import FileSessionStore

store = InMemorySessionStore()          # swap for FileSessionStore for disk
runner = Runner(RunnerConfig(agents=[agent], session_store=store))

# First turn — auto-generates session_id
result = await runner.run(
    [{'role': 'user', 'content': 'Hello!'}],
    session_id='chat-001',
)
print(result.metadata['session_id'])    # 'chat-001'

# Resume — prior history is prepended automatically
result = await runner.run(
    [{'role': 'user', 'content': 'What did I say?'}],
    session_id='chat-001',
)
```

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

Every run automatically collects token usage and timing metrics. LLM
call events are also available via callbacks.

```python
# Post-run summary
result = await AgentRuntime(agent).run(messages)
usage = result.metadata['usage']  # UsageSummary
print(usage.total_input_tokens)
print(usage.total_output_tokens)
print(usage.llm_calls)
print(usage.total_latency_ms)

# Real-time LLM call monitoring via callbacks
class MetricsCallback:
    async def on_llm_start(self, agent_name, iteration, message_count):
        print(f'[{agent_name}] iter={iteration} msgs={message_count}')

    async def on_llm_end(self, agent_name, iteration, input_tokens,
                         output_tokens, latency_ms):
        print(f'  tokens={input_tokens}+{output_tokens} {latency_ms:.0f}ms')

agent = Agent(..., callbacks=[MetricsCallback()])
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
from sonya.core import LoggingInterceptor, ClientConfig, AnthropicClient

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
