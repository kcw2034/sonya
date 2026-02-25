# Sonya

Lightweight Python AI agent framework for a tool-first execution loop.
Sonya focuses on a minimal and explicit architecture: LLM client abstraction, typed tools, and a runtime that repeatedly executes `LLM -> tool_use -> tool_result`.

Read in Korean: `README.ko.md`

## Status

- Core package (`sonya-core`) is implemented and tested.
- `src/sonya-agent/greedy/persona/` contains an agent example scaffold restored for reference work, adapted from OpenClaw.
- Current scope: single-agent runtime, tool execution loop, provider clients, streaming interface, logging helper.
- Planned next scope: state/memory, multi-agent orchestration, observability, guardrails.

## Repository Layout

```text
.
├── src/
│   ├── sonya-core/
│   │   ├── llm/           # BaseLLMClient + Anthropic/OpenAI/Gemini clients
│   │   ├── runtime/       # AgentRuntime
│   │   ├── tools/         # BaseTool, ToolRegistry, ToolContext
│   │   └── logging.py     # setup_logging helper
│   └── sonya-agent/       # product/domain layer (early stage)
├── tests/                 # pytest test suite
├── AGENTS.md              # project working rules
└── README.md
```

## Requirements

- Python 3.11+

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install for local development:

```bash
pip install -e .
pip install -e ".[dev]"
```

Or install package dependencies only:

```bash
pip install pydantic httpx python-dotenv
```

## Quick Start

```python
import asyncio
from pydantic import BaseModel, Field

from sonya_core.llm import AnthropicClient
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.base import BaseTool
from sonya_core.tools.registry import ToolRegistry


class AddInput(BaseModel):
    a: int = Field(description="first number")
    b: int = Field(description="second number")


class AddOutput(BaseModel):
    result: int


class AddTool(BaseTool[AddInput, AddOutput]):
    name = "add"
    description = "Add two numbers"

    async def execute(self, input: AddInput) -> AddOutput:
        return AddOutput(result=input.a + input.b)


async def main() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    async with AnthropicClient(system="math assistant") as client:
        agent = AgentRuntime(client=client, registry=registry)
        answer = await agent.run("What is 3 + 5?")
        print(answer)


asyncio.run(main())
```

## Streaming

```python
import asyncio

from sonya_core.llm import AnthropicClient
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.registry import ToolRegistry


async def main() -> None:
    async with AnthropicClient(system="helpful assistant") as client:
        agent = AgentRuntime(client=client, registry=ToolRegistry())
        async for token in agent.run_stream("Describe Seoul in one sentence"):
            print(token, end="", flush=True)
        print()


asyncio.run(main())
```

## Core Components

### LLM

- `BaseLLMClient`: shared provider interface.
- Clients: `AnthropicClient`, `OpenAIClient`, `GeminiClient`.
- Unified response model: `LLMResponse`, `ContentBlock`, `StopReason`, `Usage`.
- API failures are wrapped as `LLMAPIError` with retryability information.

Environment variables:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

Streaming support:

- `AnthropicClient`: native SSE streaming implementation.
- `OpenAIClient`, `GeminiClient`: fallback stream via base client (`chat` result wrapped as stream chunk).

### Tools

- `BaseTool[InputModel, OutputModel]` with Pydantic validation.
- `ToolRegistry` for registration, lookup, schema export, and batch execution.
- `ToolContext` for data sharing across tool calls within one runtime loop.
- `ToolError` for recoverable/non-recoverable tool failures.
- Built-in examples: `CalculatorTool`, `WebSearchTool` (mock), `WriteFileTool`.

### Runtime

- `AgentRuntime.run(user_message)` returns final text.
- `AgentRuntime.run_stream(user_message)` yields text tokens.
- Loop behavior handles `tool_use` automatically until `end_turn` or `max_iterations`.

### Logging

- `setup_logging(level=..., format="text" | "json")`
- JSON formatter is available for structured logs.

## Development

Run tests:

```bash
pytest
```

Run a subset:

```bash
pytest tests/test_runtime.py -v
```

## Contribution Notes

- Follow conventions in `AGENTS.md`.
- Keep changes scoped to the request.
- Prefer existing naming/style/error-handling patterns.
- Write code comments and docstrings in Korean.

## License

MIT (see `LICENSE`)
