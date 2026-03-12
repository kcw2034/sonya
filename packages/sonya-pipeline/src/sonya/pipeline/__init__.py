"""sonya-pipeline — inter-package data pipeline integration for sonya.

Bridges the data flow between sonya-pack (BinContext) and sonya-core
(Agent), providing a composable pipeline layer for external data source
integration.
"""

from .client.bridge import ContextBridge
from .client.memory import DefaultMemoryPipeline
from .client.pipeline import (
    FilterByRoleStage,
    MetadataInjectionStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)
from .schemas.types import (
    MemoryStore,
    Message,
    PipelineStage,
    SourceAdapter,
)
from .stores.bridge_store import BridgeStore
from .stores.in_memory import InMemoryStore

__all__ = [
    # Bridge
    "ContextBridge",
    # Pipeline
    "Pipeline",
    # Built-in stages
    "TruncateStage",
    "SystemPromptStage",
    "FilterByRoleStage",
    "MetadataInjectionStage",
    # Memory
    "DefaultMemoryPipeline",
    "MemoryStore",
    "InMemoryStore",
    "BridgeStore",
    # Protocols
    "PipelineStage",
    "SourceAdapter",
    "Message",
]
