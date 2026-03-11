# sonya-core

Core package of the Sonya framework. It provides thin wrappers around
official LLM SDKs, a tool system, agent runtime, and multi-agent
orchestration primitives.

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
│   │   ├── base.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── google.py
│   │   └── interceptor.py         # LoggingInterceptor
│   └── cache/                     # provider cache abstractions/impl
│       ├── base.py
│       ├── anthropic.py
│       ├── openai.py
│       └── gemini.py
├── models/                        # Agent/Tool/Runner/Supervisor models
│   ├── agent.py
│   ├── agent_runtime.py
│   ├── tool.py
│   ├── tool_registry.py
│   ├── runner.py
│   └── supervisor.py
├── parsers/                       # provider response adapters + schema parser
│   ├── adapter.py
│   └── schema_parser.py
├── schemas/                       # shared types/events/memory schemas
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

## Usage

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

Tool + AgentRuntime example:

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

## Design Principles

- **Thin wrapper**: Keep APIs simple while wrapping official SDKs
- **SDK passthrough**: `**kwargs` are forwarded directly
- **Native responses**: Return SDK-native response objects
- **Protocol-driven extension**: `Interceptor`, `AgentCallback`,
  and `MemoryPipeline` interfaces for customization

## Main APIs

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

## Example

```bash
python examples/gemini_agent_demo.py
```

`examples/gemini_agent_demo.py` includes:

- Single agent + tool calls
- Agent handoff chain (`triage -> weather_specialist`)

## Tests

```bash
pytest tests/ -v
```

Current test coverage:

- Provider clients: `test_base_client.py`
- Cache: `test_cache_anthropic.py`, `test_cache_openai.py`,
  `test_cache_gemini.py`, `test_cache_base.py`, `test_cache_types.py`
- Tool: `test_tool_decorator.py`, `test_tool_schema.py`
- Runtime/Adapter: `test_agent_runtime.py`, `test_agent_adapter.py`
- Orchestration: `test_handoff.py`, `test_supervisor.py`
- Routing/Memory: `test_context_router.py`, `test_context_memory_types.py`
- Logging/Import: `test_logging.py`, `test_imports.py`
