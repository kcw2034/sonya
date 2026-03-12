# sonya-pack

`sonya-pack` is a lightweight context storage engine built on
BinContext. It stores conversation messages in an append-only binary log
(`context.bin`) and restores only required ranges via a metadata index
(`metadata.json`).

## Features

- Append-only binary storage using `offset` and `length` pointers
- Session-level message indexing and persistence
- Recent context restoration via `last_n_turns`
- `MemoryType` filtering (`episodic`, `procedural`, `semantic`)
- Pydantic-based metadata schema validation

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
from sonya.core.schemas.memory import MemoryType
from sonya.pack import BinContextEngine

engine = BinContextEngine('./data')

engine.add_message(
    'session-1',
    'user',
    'Summarize today\'s meeting.',
)
engine.add_message(
    'session-1',
    'system',
    'Write summaries in bullet points.',
    memory_type=MemoryType.PROCEDURAL,
    workflow_name='meeting_summary',
    step_order=1,
)

recent = engine.build_context(
    'session-1',
    last_n_turns=5,
)
only_rules = engine.build_context(
    'session-1',
    memory_type=MemoryType.PROCEDURAL,
)

print(recent)
print(only_rules)
```

## Structure

```text
src/sonya/pack/
├── __init__.py
├── client/
│   └── engine.py              # BinContextEngine
└── schemas/
    └── schema.py              # MessageMeta / SessionIndex / memory meta
```

## Key Methods

- `add_message(session_id, role, content, ...)` — append a message
- `build_context(session_id, last_n_turns, memory_type)` — restore messages
- `clear_session(session_id)` — remove all messages for a session
- `list_sessions()` — list all registered session IDs

## Data Files

Files managed by the engine:

- `context.bin`: stores UTF-8 message bytes sequentially
- `metadata.json`: session-level metadata index

## Example

```bash
python examples/basic_usage.py
```

## Tests

```bash
pytest tests/ -v
```

Current test coverage:

- `test_engine_memory.py`: memory type save/filter/reload checks
- `test_memory_schemas.py`: schema checks for `EpisodicMeta`,
  `ProceduralMeta`, and `SemanticMeta`
