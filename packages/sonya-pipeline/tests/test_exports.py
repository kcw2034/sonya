"""Tests for sonya.pipeline public exports."""


def test_memory_exports():
    from sonya.pipeline import (
        DefaultMemoryPipeline,
        InMemoryStore,
        BridgeStore,
    )
    assert DefaultMemoryPipeline is not None
    assert InMemoryStore is not None
    assert BridgeStore is not None


def test_memory_store_protocol_export():
    from sonya.pipeline import MemoryStore
    assert MemoryStore is not None


def test_existing_exports_preserved():
    from sonya.pipeline import (
        ContextBridge,
        Pipeline,
        TruncateStage,
        SystemPromptStage,
        FilterByRoleStage,
        MetadataInjectionStage,
        PipelineStage,
        SourceAdapter,
        Message,
    )
    assert all([
        ContextBridge, Pipeline, TruncateStage,
        SystemPromptStage, FilterByRoleStage,
        MetadataInjectionStage, PipelineStage,
        SourceAdapter, Message,
    ])
