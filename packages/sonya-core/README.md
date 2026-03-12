# sonya-core

Core package of the Sonya framework. Thin wrappers around official LLM
SDKs with a tool system, agent runtime, and multi-agent orchestration.

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
├── models/                        # Agent/Tool/Runner/Supervisor models
│   ├── agent.py                   # Agent, AgentResult
│   ├── agent_runtime.py           # AgentRuntime (run / run_stream)
│   ├── tool.py                    # Tool, ToolResult
│   ├── tool_registry.py
│   ├── runner.py                  # Runner, RunnerConfig
│   ├── supervisor.py
│   └── prompt.py                  # Prompt, Example
├── parsers/                       # provider response adapters + schema parser
│   ├── adapter.py
│   └── schema_parser.py
├── schemas/                       # shared types/events/memory schemas
│   ├── types.py                   # ClientConfig, GuardrailConfig, RetryConfig,
│   │                              # UsageSummary, AgentCallback, Interceptor
│   ├── events.py
│   └── memory.py                  # NormalizedMessage, MemoryPipeline
├── utils/
│   ├── decorator.py               # @tool decorator
│   ├── tool_context.py
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

Limit cumulative tool calls and total tool execution time per run.

```python
from sonya.core import Agent, GuardrailConfig

agent = Agent(
    name='safe_agent',
    client=client,
    tools=[search, fetch],
    guardrails=GuardrailConfig(
        max_tool_calls=10,
        max_tool_time=30.0,  # seconds
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

```python
result = await AgentRuntime(agent).run(messages)
usage = result.metadata['usage']  # UsageSummary

print(usage.total_input_tokens)   # sum across all LLM calls
print(usage.total_output_tokens)
print(usage.llm_calls)            # number of generate() invocations
print(usage.iterations)           # agent loop iterations
print(usage.total_tool_calls)
print(usage.total_tool_time_ms)   # ms
print(usage.total_latency_ms)     # cumulative LLM round-trip ms
```

`extract_usage(response)` is also available as a standalone utility:

```python
from sonya.core.client.provider.interceptor import extract_usage

inp, out = extract_usage(response)  # works with Anthropic/OpenAI/Gemini
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
- **Observability**: `UsageSummary`
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

Current test coverage:

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
- Orchestration: `test_handoff.py`, `test_supervisor.py`
- Routing/Memory: `test_context_router.py`, `test_context_memory_types.py`
- Logging/Import: `test_logging.py`, `test_imports.py`
