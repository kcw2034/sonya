# sonya-core

`sonya-core` is a lightweight Python AI agent framework focused on a tool-first execution loop.

## Features

- Type-safe tools with `BaseTool[InputModel, OutputModel]`
- Unified LLM response model (`LLMResponse`, `ContentBlock`)
- Built-in tool loop runtime (`AgentRuntime.run`)
- Streaming runtime with tool loop (`AgentRuntime.run_stream`)
- Minimal dependencies (`pydantic`, `httpx`)

## Installation

```bash
pip install sonya-core
```

Install with development extras:

```bash
pip install "sonya-core[dev]"
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
        runtime = AgentRuntime(client=client, tools=registry)
        answer = await runtime.run("What is 3 + 5?")
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
        runtime = AgentRuntime(client=client, tools=ToolRegistry())

        async for token in runtime.run_stream("Describe Seoul in one sentence"):
            print(token, end="", flush=True)

        print()


asyncio.run(main())
```

`run_stream()` yields text deltas and continues the loop automatically when `tool_use` appears.

## Environment Variables

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

You can also pass `api_key` directly to each client constructor.

## Supported Providers

- `AnthropicClient`
- `OpenAIClient`
- `GeminiClient`

## Test

```bash
pytest
```

## Requirements

- Python 3.11+
