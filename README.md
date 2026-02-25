# Sonya

Lightweight general-purpose AI agent framework based on Python. Build tool-based agents on any LLM provider with minimal dependencies and a simple API.

*Read this in other languages: [English](README.md), [한국어](README.ko.md)*

> **Current Status**: Core layer (Tool + LLM + Basic Runtime) implementation complete. Major features such as state management, multi-agent, and observability are planned — approximately **20~25%** progress relative to the full roadmap.

## Repository Structure

```text
.
├── src/
│   ├── sonya-core/        # Core package for PyPI distribution
│   │   ├── llm/           # BaseLLMClient + Anthropic/OpenAI/Gemini implementations
│   │   ├── runtime/       # AgentRuntime (run / run_stream)
│   │   └── tools/         # BaseTool, ToolRegistry, ToolContext, built-in examples
│   └── sonya-agent/       # Product/domain-specific layer (initial state)
├── tests/                 # Core tests (70+ cases, 6 files)
├── AGENTS.md              # Task/coding rules
└── README.md              # This document
```

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r src/sonya-core/requirements.txt
```

```python
import asyncio
from pydantic import BaseModel, Field

from sonya_core.llm import AnthropicClient
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.base import BaseTool
from sonya_core.tools.registry import ToolRegistry


class CalcInput(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")

class CalcOutput(BaseModel):
    result: float

class AddTool(BaseTool[CalcInput, CalcOutput]):
    name = "add"
    description = "Adds two numbers"

    async def execute(self, input: CalcInput) -> CalcOutput:
        return CalcOutput(result=input.a + input.b)


async def main() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    async with AnthropicClient(system="Math Assistant") as client:
        agent = AgentRuntime(client=client, registry=registry)
        answer = await agent.run("What is 3 plus 5?")
        print(answer)

asyncio.run(main())
```

Streaming:

```python
async with AnthropicClient(system="helpful assistant") as client:
    agent = AgentRuntime(client=client, registry=ToolRegistry())
    async for token in agent.run_stream("Describe Seoul in one sentence"):
        print(token, end="", flush=True)
```

## Current Implementation (sonya-core)

### LLM Client Abstraction

Three provider clients implemented on top of the `BaseLLMClient` interface:

| Client | Environment Variable | Streaming |
|---|---|---|
| `AnthropicClient` | `ANTHROPIC_API_KEY` | Native Streaming |
| `OpenAIClient` | `OPENAI_API_KEY` | Native Streaming |
| `GeminiClient` | `GEMINI_API_KEY` | Fallback (Non-streaming) |

All clients support `async with` context managers and unify responses into `LLMResponse`.

### Tool System

- `BaseTool[InputT, OutputT]` — Define Input/Output types using Pydantic generics
- `to_llm_schema(provider=)` — Automatically extract JSON Schema in Anthropic/OpenAI format from Pydantic models
- `safe_execute()` — Integrated validation + execution + error handling
- `ToolRegistry` — Name-based tool management, parallel execution (`execute_many`), lifecycle (`startup/shutdown`)
- `ToolContext` — Data sharing between tools within a single `run()` call scope
- `ToolError(recoverable=True/False)` — Includes whether the LLM can retry
- Automatic asynchronous wrapping for sync `execute()` (`asyncio.to_thread`)

Built-in example tools: `CalculatorTool`, `WebSearchTool` (mock), `WriteFileTool`

### Agent Runtime

Repeats the `user → LLM → tool_use → tool_result → LLM` loop up to `max_iterations`:

- `run(user_message)` — Returns the final text response
- `run_stream(user_message)` — Token-level streaming, automatic tool loop handling
- `reset()` — Resets conversation history
- `history` property — Read current conversation history

---

## Roadmap (TODO)

Aims for a production agent framework at the level of LangGraph or Google ADK.

### Progress Matrix

| Category | Sonya | LangGraph | Google ADK | Progress |
|---|---|---|---|---|
| LLM Client Abstraction | 3 Providers | Many | Gemini + LiteLLM | ~60% |
| Tool System | Complete | Complete | Complete | ~80% |
| Agent Runtime (Single) | Basic Loop | Graph-based | Event-based | ~50% |
| State/Memory | Not Implemented | Complete | Complete | ~5% |
| Multi-Agent | Not Implemented | Complete | Complete | 0% |
| Human-in-the-Loop | Not Implemented | Complete | Partial | 0% |
| Observability/Tracing | Not Implemented | LangSmith | Cloud Trace | 0% |
| Guardrails/Safety | Not Implemented | Integrated | Callback-based | 0% |
| Streaming | Token Streaming | Event Streaming | Multimodal | ~30% |
| Deployment Tools | Not Implemented | Platform | Vertex AI | 0% |
| Evaluation Framework | Not Implemented | LangSmith | Built-in | 0% |

---

### Phase 1: Core Stabilization

Refining the current implementation to a deployable level.

- [ ] **Package Distribution Structure** — Organize `pyproject.toml`, prepare for PyPI distribution
- [ ] **Real WebSearch Tool API Integration** — Connect real search APIs like Serper or Tavily (currently mock)
- [ ] **Gemini Client Streaming** — Switch from current fallback to native SSE streaming
- [ ] **Enhanced Error Handling** — Error recovery during streaming, exponential backoff retry logic
- [ ] **Tool Output Schema Validation** — Add OutputModel validation
- [ ] **Logging System Integration** — Structured logging, level-based configuration

---

### Phase 2: State & Memory

Currently, `AgentRuntime` only maintains in-memory history and lacks state persistence across sessions.

- [ ] **Session-based State Management (`SessionService`)**
  - LangGraph: Thread-based state + Checkpointer
  - Google ADK: `session.state` + `user:/app:` scope separation
  - Sonya Goal: State lookup/update service based on session_id
- [ ] **Conversation History Persistence**
  - SQLite/Postgres backends
  - History restoration upon session resumption
- [ ] **Long-term Memory System (cross-session)**
  - LangGraph: LangMem / Store
  - Google ADK: `MemoryService`
  - Sonya Goal: Semantic memory search based on Vector DB
- [ ] **Checkpointing / Execution State Save-Restore**
  - LangGraph: Automatic save at every super-step, time-travel debugging
  - Google ADK: Event-based checkpoints

---

### Phase 3: Multi-Agent Orchestration

Currently supports only a single agent loop.

- [ ] **Agent Hierarchical Structure (parent-child)**
  - LangGraph: Sub-graph composition
  - Google ADK: `sub_agents` list + `transfer_to_agent()`
  - Sonya Goal: Pattern where parent agent calls child agent as a tool
- [ ] **Workflow Agent Patterns**
  - Sequential Agent — Execute agent chain in a fixed order
  - Parallel Agent — Execute multiple agents in parallel and aggregate results
  - Loop Agent — Repeatedly execute agent until conditions are met
- [ ] **Inter-agent Communication Protocol** — Standardize message formats
- [ ] **Dynamic Routing** — Pattern where LLM selects the next agent
- [ ] **A2A (Agent-to-Agent) Protocol Support** — Interoperability with external agents

---

### Phase 4: Human-in-the-Loop

No mechanism for human intervention during agent execution.

- [ ] **Interrupt/Resume**
  - LangGraph: `interrupt()` + `Command(resume=...)`
  - Google ADK: Callback-based interruption
  - Sonya Goal: `await agent.interrupt()` / `agent.resume(value)` APIs
- [ ] **Approval/Rejection/Modification Pattern before Tool Execution**
  - Request user confirmation before executing sensitive tools (file writing, API calls, etc.)
- [ ] **Wait for and Inject User Input**
  - Pattern to pause execution and wait for input when the agent requests additional information

---

### Phase 5: Observability & Safety

Currently uses only standard Python `logging`, lacking structured tracing/auditing.

- [ ] **Execution Tracing System**
  - LangGraph: LangSmith integration
  - Google ADK: Cloud Trace + 3-layer architecture
  - Sonya Goal: Span-based tracing, OpenTelemetry compatible
- [ ] **Callback/Middleware System**
  - `before_agent` / `after_agent`
  - `before_tool` / `after_tool`
  - `before_model` / `after_model`
- [ ] **Guardrails**
  - Input/Output filtering
  - Content safety checks
  - Policy-based tool execution control
- [ ] **Token/Cost Tracking** — Usage aggregation and cost calculation per provider

---

### Phase 6: Streaming & Deployment

Currently supports only text token streaming.

- [ ] **Event Streaming** — Node entry/exit, tool execution start/complete, state change events
- [ ] **SSE (Server-Sent Events) Support** — HTTP streaming endpoints
- [ ] **MCP (Model Context Protocol) Tool Support** — Bridge tools from MCP servers as `BaseTool`
- [ ] **CLI Development Server** — Run local agent server with `sonya serve` command
- [ ] **Container Deployment Guide** — Docker, Cloud Run deployment recipes

---

### Phase 7: Evaluation

No system for measuring agent quality.

- [ ] **Agent Evaluation Framework**
  - LangGraph: LangSmith evaluation features
  - Google ADK: Built-in evaluation pipeline
  - Sonya Goal: Quality/relevance/accuracy metrics, trajectory evaluation (tool selection strategy analysis)
- [ ] **Benchmark Dataset Support** — Integration with standard agent benchmarks
- [ ] **Regression Test Automation** — Detect agent behavior regressions per PR

---

## Testing

```bash
pytest
```

6 files, 70+ test cases:

| File | Target |
|---|---|
| `test_tools.py` | BaseTool, ToolRegistry, ToolContext |
| `test_llm_models.py` | LLMResponse, Message, ContentBlock |
| `test_llm_client.py` | AnthropicClient |
| `test_openai_client.py` | OpenAIClient |
| `test_runtime.py` | AgentRuntime (run / run_stream) |
| `test_extensions.py` | Extension/Integration scenarios |

## Contribution Guide

- Prioritize existing patterns and naming conventions.
- When adding a new tool, inherit from `BaseTool[InputModel, OutputModel]` and implement `name`, `description`, and `execute()`.
- Use Pydantic `Field(description=...)` to specify parameter descriptions for the LLM.
- Write code comments and docstrings in Korean.
- Always run relevant tests after making changes.
- Avoid refactoring outside the requested scope.
- Detailed rules are based on `AGENTS.md`.

## Documentation

- Detailed core package documentation: `src/sonya-core/README.md`
- Task/coding rules: `AGENTS.md`
