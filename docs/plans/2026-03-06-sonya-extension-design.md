# sonya-extension Design

## Overview

Bidirectional integration package between sonya-core and LangChain.

## Components

| ID | Direction | Description |
|----|-----------|-------------|
| B  | sonya → LC | `to_langchain_tool()` — sonya Tool → LangChain StructuredTool |
| C  | sonya → LC | `SonyaChatModel(BaseChatModel)` — sonya BaseClient as LangChain ChatModel |
| D  | LC → sonya | `to_sonya_tool()` — LangChain BaseTool → sonya Tool |
| E  | LC → sonya | `LangChainClient(BaseClient)` — LangChain ChatModel as sonya BaseClient |

## Package Structure

```
packages/sonya-extension/
├── pyproject.toml
└── src/sonya/extension/
    ├── __init__.py
    ├── client/
    │   ├── __init__.py
    │   └── langchain_client.py   # LangChainClient + LangChainAdapter
    ├── models/
    │   ├── __init__.py
    │   └── langchain_model.py    # SonyaChatModel
    ├── schemas/
    │   ├── __init__.py
    │   └── types.py              # Shared types
    └── utils/
        ├── __init__.py
        └── tool_converter.py     # to_sonya_tool(), to_langchain_tool()
```

## Dependencies

- Required: `sonya-core>=0.0.1`
- Optional: `langchain-core>=0.3`

## Key Design Decisions

- LangChain is optional to keep the package lightweight
- Uses `langchain-core` (not `langchain`) to minimize dependency footprint
- LangChainAdapter implements ResponseAdapter protocol for AgentRuntime compatibility
- Message format conversion is centralized in schemas/types.py
