# sonya-core

Core package of the Sonya framework. Thin wrappers around official LLM
SDKs with a tool system, agent runtime, session persistence, and
multi-agent orchestration.

## Installation

```bash
# specific provider
pip install -e ".[anthropic]"
pip install -e ".[openai]"
pip install -e ".[gemini]"

# all providers + dev dependencies
pip install -e ".[all,dev]"
```

## Structure

```text
src/sonya/core/
├── __init__.py                    # public API exports
├── client/
│   ├── provider/                  # Anthropic/OpenAI/Gemini thin clients
│   │   ├── base.py                # BaseClient (retry, interceptor chain)
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── google.py
│   │   └── interceptor.py         # LoggingInterceptor, extract_usage()
│   └── cache/                     # provider cache abstractions/impl
│       ├── base.py
│       ├── anthropic.py
│       ├── openai.py
│       └── gemini.py
├── models/                        # Agent/Tool/Runner/Supervisor/Session models
│   ├── agent.py                   # Agent, AgentResult
│   ├── agent_runtime.py           # AgentRuntime (run / run_stream)
│   ├── tool.py                    # Tool, ToolResult
│   ├── tool_registry.py           # ToolRegistry (register/unregister/has/clear)
│   ├── runner.py                  # Runner, RunnerConfig (session_store support)
│   ├── session.py                 # Session, SessionStore protocol
│   ├── supervisor.py
│   └── prompt.py                  # Prompt, Example
├── stores/                        # session store implementations
│   └── in_memory.py               # InMemorySessionStore
├── parsers/                       # provider response adapters + schema parser
│   ├── adapter.py
│   └── schema_parser.py           # ToolContext params excluded automatically
├── schemas/                       # shared types/events/memory schemas
│   ├── types.py                   # ClientConfig, GuardrailConfig, RetryConfig,
│   │                              # UsageSummary, AgentCallback, Interceptor
│   ├── events.py
│   └── memory.py                  # NormalizedMessage, MemoryPipeline
├── utils/
│   ├── decorator.py               # @tool decorator
│   ├── tool_context.py            # ToolContext (shared state + add/remove_tool)
│   ├── router.py
│   ├── callback.py                # DebugCallback
│   ├── handoff.py
│   └── validation.py
└── exceptions/
    └── errors.py                  # AgentError, ToolError, GuardrailError,
                                   # MaxRetriesExceededError, ToolApprovalDeniedError
```

## Quick Start

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

## Agent with Tools

```python
import asyncio
from sonya.core import Agent, AgentRuntime, ClientConfig, OpenAIClient, tool

@tool(description='Add two integers')
def add(a: int, b: int) -> int:
    return a + b

async def main() -> None:
    client = OpenAIClient(ClientConfig(model='gpt-4o'))
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

## ToolContext — Shared State & Dynamic Registration

Tool functions can declare a `context: ToolContext` parameter to read and
write run-scoped shared state. This parameter is injected automatically at
runtime and **never appears in the LLM tool schema**.

```python
from sonya.core import tool, ToolContext

@tool(description='Search and cache the query')
async def search(query: str, context: ToolContext) -> str:
    context.set('last_query', query)
    return f'Results for: {query}'

@tool(description='Return the last search query')
async def recall(context: ToolContext) -> str:
    return context.get('last_query', 'none')
```

Tools can also register new tools mid-run:

```python
@tool()
async def bootstrap(context: ToolContext) -> str:
    @tool()
    async def dynamic(x: str) -> str:
        """Registered at runtime."""
        return x
    context.add_tool(dynamic)   # visible in the next LLM iteration
    return 'dynamic tool registered'
```

## Session Persistence

Resume conversations across runs or process restarts.

```python
from sonya.core import Runner, RunnerConfig, InMemorySessionStore
# from sonya.pipeline.stores.file_session_store import FileSessionStore  # disk

store = InMemorySessionStore()
runner = Runner(RunnerConfig(agents=[agent], session_store=store))

# First turn
result = await runner.run(
    [{'role': 'user', 'content': 'Hello!'}],
    session_id='chat-001',
)

# Resume — prior history automatically prepended
result = await runner.run(
    [{'role': 'user', 'content': 'What did I say?'}],
    session_id='chat-001',
)
print(result.metadata['session_id'])  # 'chat-001'
```

## Streaming

`run_stream()` yields text chunks as they are produced, then yields the
final `AgentResult` as the last item.

```python
from sonya.core import Agent, AgentRuntime, AgentResult

async for item in AgentRuntime(agent).run_stream(messages):
    if isinstance(item, str):
        print(item, end='', flush=True)
    elif isinstance(item, AgentResult):
        result = item  # final result with full history
```

## Retry & Resilience

`RetryConfig` controls exponential-backoff retry on network errors.

```python
from sonya.core import ClientConfig, RetryConfig, AnthropicClient

config = ClientConfig(
    model='claude-sonnet-4-6',
    retry=RetryConfig(
        max_retries=5,
        base_delay=0.5,
        backoff_factor=2.0,
    ),
)
client = AnthropicClient(config)
```

## Guardrails

Limit cumulative tool calls, total tool execution time, and concurrent
tool executions per run.

```python
from sonya.core import Agent, GuardrailConfig

agent = Agent(
    name='safe_agent',
    client=client,
    tools=[search, fetch],
    guardrails=GuardrailConfig(
        max_tool_calls=10,
        max_tool_time=30.0,         # seconds
        max_concurrent_tools=3,
    ),
)
```

## Structured Output

Pass a JSON Schema to enforce a specific response shape. The runtime
auto-retries on parse/validation failure.

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

## Human-in-the-Loop

Mark tools as requiring approval. The runtime calls
`AgentCallback.on_approval_request` before execution; returning `False`
feeds an error result back to the LLM instead of running the tool.

```python
from sonya.core import tool, Agent

@tool(description='Delete a file', requires_approval=True)
async def delete_file(path: str) -> str:
    ...

class ApprovalCallback:
    async def on_approval_request(
        self, agent_name: str, tool_name: str, arguments: dict
    ) -> bool:
        answer = input(f'Allow {tool_name}({arguments})? [y/N] ')
        return answer.lower() == 'y'

agent = Agent(
    name='file_agent',
    client=client,
    tools=[delete_file],
    callbacks=[ApprovalCallback()],
)
```

## Observability

Every `AgentResult` carries a `UsageSummary` in `metadata['usage']`
with token counts, LLM call count, iteration count, and tool timing.
Real-time LLM events are delivered via `on_llm_start` / `on_llm_end`
callbacks.

```python
# Post-run aggregate
result = await AgentRuntime(agent).run(messages)
usage = result.metadata['usage']  # UsageSummary

print(usage.total_input_tokens)   # sum across all LLM calls
print(usage.total_output_tokens)
print(usage.llm_calls)            # number of generate() invocations
print(usage.iterations)           # agent loop iterations
print(usage.total_tool_calls)
print(usage.total_tool_time_ms)   # ms
print(usage.total_latency_ms)     # cumulative LLM round-trip ms

# Real-time LLM monitoring
class MyCallback:
    async def on_llm_start(
        self, agent_name: str, iteration: int, message_count: int
    ) -> None:
        print(f'LLM call #{iteration} with {message_count} messages')

    async def on_llm_end(
        self, agent_name: str, iteration: int,
        input_tokens: int, output_tokens: int, latency_ms: float,
    ) -> None:
        print(f'  → {input_tokens}+{output_tokens} tokens, {latency_ms:.0f}ms')
```

## Dynamic Tool Registry

`ToolRegistry` supports runtime management of tools:

```python
from sonya.core import ToolRegistry

registry = ToolRegistry()
registry.register(my_tool)
registry.register_many([tool_a, tool_b])
registry.has('my_tool')       # True
registry.unregister('my_tool')
registry.clear()
```

## Main APIs

- **Client**: `BaseClient`, `AnthropicClient`, `OpenAIClient`, `GeminiClient`
- **Config**: `ClientConfig`, `RetryConfig`
- **Cache**: `BaseCache`, `AnthropicCache`, `OpenAICache`, `GeminiCache`,
  `CacheConfig`, `CacheUsage`
- **Tool**: `tool`, `Tool`, `ToolResult`, `ToolRegistry`, `ToolContext`
- **Agent**: `Agent`, `AgentResult`, `AgentRuntime`
- **Guardrails**: `GuardrailConfig`, `GuardrailError`
- **Structured Output**: `Agent(output_schema=...)`
- **Observability**: `UsageSummary`, `AgentCallback.on_llm_start/on_llm_end`
- **Session**: `Session`, `SessionStore`, `InMemorySessionStore`
- **Orchestration**: `Runner`, `RunnerConfig`, `RunnerCallback`,
  `SupervisorRuntime`, `SupervisorConfig`
- **Routing/Memory**: `ContextRouter`, `MemoryType`, `MemoryEntry`,
  `NormalizedMessage`, `MemoryPipeline`
- **Logging**: `LoggingInterceptor`, `DebugCallback`
- **Errors**: `AgentError`, `ToolError`, `GuardrailError`,
  `MaxRetriesExceededError`, `ToolApprovalDeniedError`
- **Protocols**: `Interceptor`, `AgentCallback`

## Design Principles

- **Thin wrapper**: Keep APIs simple while wrapping official SDKs
- **SDK passthrough**: `**kwargs` forwarded directly to provider
- **Native responses**: Return SDK-native response objects
- **Protocol-driven extension**: `Interceptor`, `AgentCallback`,
  and `MemoryPipeline` interfaces for customization

## Tests

```bash
pytest tests/ -v
```

Current test coverage (531 tests):

- Provider clients: `test_base_client.py`, `test_base_client_retry.py`
- Cache: `test_cache_anthropic.py`, `test_cache_openai.py`,
  `test_cache_gemini.py`, `test_cache_base.py`, `test_cache_types.py`
- Tool: `test_tool_decorator.py`, `test_tool_schema.py`
- Runtime/Adapter: `test_agent_runtime.py`, `test_agent_runtime_stream.py`,
  `test_agent_adapter.py`
- Guardrails: `test_guardrails.py`
- Structured Output: `test_structured_output.py`
- Human-in-the-Loop: `test_human_in_the_loop.py`
- Observability: `test_observability.py`
- LLM Callbacks: `test_llm_callbacks.py`
- ToolContext Injection: `test_tool_context_injection.py`
- Dynamic Tool Registry: `test_dynamic_tool_registry.py`,
  `test_dynamic_tool_context.py`
- Session: `test_session.py`, `test_session_runner.py`
- Parallel Tool Execution: `test_parallel_tool_execution.py`
- Orchestration: `test_handoff.py`, `test_supervisor.py`
- Routing/Memory: `test_context_router.py`, `test_context_memory_types.py`
- Exports/Import: `test_top_level_exports.py`, `test_logging.py`,
  `test_imports.py`
