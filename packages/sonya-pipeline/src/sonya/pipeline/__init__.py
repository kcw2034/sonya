"""sonya-pipeline — inter-package data pipeline integration for sonya.

Bridges the data flow between sonya-pack (BinContext) and sonya-core
(Agent), providing a composable pipeline layer for external data source
integration.
"""

from sonya.pipeline.client.bridge import ContextBridge
from sonya.pipeline.client.memory import DefaultMemoryPipeline
from sonya.pipeline.client.pipeline import (
    FilterByRoleStage,
    MetadataInjectionStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)
from sonya.pipeline.schemas.types import (
    MemoryStore,
    Message,
    PipelineStage,
    SourceAdapter,
)
from sonya.pipeline.stores.bridge_store import BridgeStore
from sonya.pipeline.stores.in_memory import InMemoryStore

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
