# sonya-pipeline

Pipeline package connecting `sonya-pack` (BinContext storage) and
`sonya-core` (Agent). It normalizes messages across providers, transforms
them through a stage chain, and persists cross-provider session context
including tool calls and tool results.

## Features

- `ContextBridge`: BinContextEngine ↔ Agent message bridge
- `Pipeline`: sequential stage engine for message transformation
- `DefaultMemoryPipeline`: cross-provider normalization and reconstruction
  — supports **Anthropic**, **OpenAI**, and **Gemini** including
  `tool_calls` and `tool_results`
- `InMemoryStore`: in-process session store for testing / short-lived sessions
- `BridgeStore`: durable session store backed by BinContext (persists
  tool_calls and tool_results)
- Built-in stages: `TruncateStage`, `SystemPromptStage`,
  `FilterByRoleStage`, `MetadataInjectionStage`
- Protocol-based extension: `PipelineStage`, `SourceAdapter`, `MemoryStore`

## Installation

```bash
pip install -e .
```

With development dependencies:

```bash
pip install -e ".[dev]"
```

## Usage

### Pipeline — message transformation stages

```python
from sonya.pack import BinContextEngine
from sonya.pipeline import (
    ContextBridge,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)

engine = BinContextEngine('./data')
bridge = ContextBridge(engine)

bridge.save_messages(
    'session-1',
    [
        {'role': 'user', 'content': 'Tell me Seoul weather.'},
        {'role': 'assistant', 'content': 'Sunny, 8°C.'},
    ],
)

messages = bridge.load_context('session-1')

pipeline = Pipeline()
pipeline.add_stage(SystemPromptStage('You are a concise assistant.'))
pipeline.add_stage(TruncateStage(max_turns=6))

agent_input = pipeline.run(messages)
```

### DefaultMemoryPipeline — cross-provider normalization

Normalize from one provider, reconstruct for another. Tool calls and
tool results are preserved across the conversion.

```python
from sonya.pipeline import DefaultMemoryPipeline, InMemoryStore

store = InMemoryStore()
pipeline = DefaultMemoryPipeline(store=store)

# Anthropic history with a tool call
anthropic_history = [
    {
        'role': 'assistant',
        'content': [
            {'type': 'text', 'text': 'Searching...'},
            {
                'type': 'tool_use',
                'id': 'tc_1',
                'name': 'search',
                'input': {'q': 'Seoul weather'},
            },
        ],
    }
]

# Normalize and save
pipeline.save_session('s1', anthropic_history, 'anthropic')

# Load and reconstruct for OpenAI — tool_calls preserved
openai_messages = pipeline.load_session('s1', 'openai')
# openai_messages[0]['tool_calls'][0]['function']['name'] == 'search'
```

### Cross-provider conversion (without store)

```python
normalized = pipeline.normalize(anthropic_history, 'anthropic')
gemini_messages = pipeline.reconstruct(normalized, 'gemini')
```

### BridgeStore — durable session persistence

```python
from sonya.pack import BinContextEngine
from sonya.pipeline import ContextBridge, BridgeStore, DefaultMemoryPipeline

engine = BinContextEngine('./data')
bridge = ContextBridge(engine)
store = BridgeStore(bridge)

pipeline = DefaultMemoryPipeline(store=store)
pipeline.save_session('session-1', history, 'anthropic')
restored = pipeline.load_session('session-1', 'openai')
```

## Structure

```text
src/sonya/pipeline/
├── __init__.py
├── client/
│   ├── bridge.py              # ContextBridge
│   ├── memory.py              # DefaultMemoryPipeline
│   └── pipeline.py            # Pipeline + built-in stages
├── schemas/
│   └── types.py               # MemoryStore / PipelineStage / SourceAdapter
└── stores/
    ├── in_memory.py           # InMemoryStore
    └── bridge_store.py        # BridgeStore (BinContext-backed)
```

## Provider Support Matrix

| Provider  | Text | tool_calls | tool_results |
|-----------|------|------------|--------------|
| Anthropic | ✅   | ✅ (`tool_use` / `tool_result` blocks) | ✅ |
| OpenAI    | ✅   | ✅ (`tool_calls` array / `role='tool'`) | ✅ |
| Gemini    | ✅   | ✅ (`function_call` parts) | ✅ (`function_response` parts) |

Cross-provider roundtrips (e.g., Anthropic → OpenAI, OpenAI → Gemini)
preserve tool call IDs and arguments. Gemini has no native call IDs;
synthetic IDs (`gemini_call_N`) are assigned during normalization.

## Tests

```bash
pytest tests/ -v
```

Current test coverage:

- `test_in_memory_store.py` — InMemoryStore save/load/clear
- `test_bridge_store.py` — BridgeStore with BinContext delegation
- `test_bridge_store_tool_calls.py` — tool_calls/tool_results persistence
- `test_memory_store_protocol.py` — MemoryStore protocol compliance
- `test_memory_pipeline_normalize.py` — provider-specific normalization
- `test_memory_pipeline_reconstruct.py` — reconstruction and roundtrips
- `test_memory_pipeline_tool_calls.py` — tool_calls normalize/reconstruct,
  cross-provider conversion
- `test_memory_pipeline_session.py` — session save/load with store
- `test_integration_memory.py` — end-to-end flows
- `test_exports.py` — public API exports
