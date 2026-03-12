"""sonya.pipeline.client — Pipeline engine and context bridge."""

from .bridge import ContextBridge
from .pipeline import (
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
