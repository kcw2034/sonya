"""sonya-pipeline — sonya 패키지 간 데이터 파이프라인 통합

sonya-pack(BinContext) ↔ sonya-core(Agent) 사이의 데이터 흐름을 연결하고,
외부 데이터 소스와의 통합을 위한 파이프라인 모듈.
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
