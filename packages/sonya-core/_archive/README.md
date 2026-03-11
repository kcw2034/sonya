# sonya-core (archive)

Legacy implementation archive for the pre-`sonya.core` rewrite.
This directory is kept for reference only and is not the active runtime.

## Status

- Archived: no new feature development
- Kept for migration reference and historical context
- Active implementation lives in `packages/sonya-core/src/sonya/core/`

## Preserved Scope

- Legacy provider clients under `llm/` (Anthropic/OpenAI/Gemini)
- Legacy tool system based on `BaseTool[InputT, OutputT]`
- Legacy runtime loop in `runtime/agent.py`
- Legacy registry/context utilities in `tools/` and `runtime/context/`

## Layout

```text
_archive/
├── llm/                         # Legacy LLM client/model layer
│   ├── client/
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   └── google.py
│   ├── base.py
│   ├── models.py
│   └── schema.py
├── runtime/
│   ├── agent.py                 # Legacy AgentRuntime (run/run_stream)
│   └── context/
│       └── history.py
├── tools/
│   ├── base.py                  # BaseTool generic
│   ├── registry.py
│   ├── context.py
│   └── models.py
├── logging.py
├── NAMING_CONVENTIONS.md
└── PROGRESS.md
```

## Migration Note

For new development:

- Use `sonya.core` API (`from sonya.core import ...`)
- Follow the active package README:
  `packages/sonya-core/README.md`

For legacy code maintenance:

- Keep imports pinned to archived module paths used at the time
- Avoid mixing archived APIs with the new runtime in one code path

## Requirements

- Python 3.11+
