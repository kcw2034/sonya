"""sonya.pipeline.client — Pipeline engine and context bridge."""

from sonya.pipeline.client.bridge import ContextBridge
from sonya.pipeline.client.pipeline import (
    FilterByRoleStage,
    MetadataInjectionStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)

__all__ = [
    'ContextBridge',
    'FilterByRoleStage',
    'MetadataInjectionStage',
    'Pipeline',
    'SystemPromptStage',
    'TruncateStage',
]
