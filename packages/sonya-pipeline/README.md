# sonya-pipeline

Pipeline package that connects data flow between `sonya-pack` and
`sonya-core`. It can load messages from BinContext storage, transform
them through a stage chain, and produce agent-ready message inputs.

## Features

- `ContextBridge`: BinContextEngine <-> Agent message bridge
- `Pipeline`: sequential stage engine for message lists
- Built-in stages: `TruncateStage`, `SystemPromptStage`,
  `FilterByRoleStage`, `MetadataInjectionStage`
- Protocol-based extension points: `PipelineStage`, `SourceAdapter`

## Installation

```bash
pip install -e .
```

With development dependencies:

```bash
pip install -e ".[dev]"
```

## Usage

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
pipeline.add_stage(
    SystemPromptStage(
        'You are a concise assistant.'
    )
)
pipeline.add_stage(TruncateStage(max_turns=6))

agent_input = pipeline.run(messages)
print(agent_input)
```

## Structure

```text
src/sonya/pipeline/
├── __init__.py
├── client/
│   ├── bridge.py              # ContextBridge
│   └── pipeline.py            # Pipeline + built-in stages
└── schemas/
    └── types.py               # Message / PipelineStage / SourceAdapter
```

## Tests

`tests/` currently includes only scaffold files (`__init__.py`).
Package-specific test cases are planned.
