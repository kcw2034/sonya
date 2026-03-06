"""sonya-pipeline — sonya 패키지 간 데이터 파이프라인 통합

sonya-pack(BinContext) ↔ sonya-core(Agent) 사이의 데이터 흐름을 연결하고,
외부 데이터 소스와의 통합을 위한 파이프라인 모듈.
"""

from sonya.pipeline.client.bridge import ContextBridge
from sonya.pipeline.client.pipeline import (
    FilterByRoleStage,
    MetadataInjectionStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)
from sonya.pipeline.schemas.types import (
    Message,
    PipelineStage,
    SourceAdapter,
)

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
    # Protocols
    "PipelineStage",
    "SourceAdapter",
    "Message",
]
