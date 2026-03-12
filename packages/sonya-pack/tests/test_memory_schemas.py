"""Tests for memory hierarchy schemas."""

from __future__ import annotations


from sonya.core.schemas.memory import MemoryEntry, MemoryType
from sonya.pack.schemas.schema import (
    EpisodicMeta,
    MessageMeta,
    ProceduralMeta,
    SemanticMeta,
)


class TestMessageMetaMemoryType:
    """Verify MessageMeta has memory_type field."""

    def test_default_memory_type(self) -> None:
        meta = MessageMeta(
            role='user', offset=0, length=10
        )
        assert meta.memory_type == MemoryType.EPISODIC

    def test_explicit_memory_type(self) -> None:
        meta = MessageMeta(
            role='user',
            offset=0,
            length=10,
            memory_type=MemoryType.PROCEDURAL,
        )
        assert meta.memory_type == MemoryType.PROCEDURAL


class TestEpisodicMeta:
    """Verify EpisodicMeta subclass."""

    def test_defaults(self) -> None:
        meta = EpisodicMeta(role='user', offset=0, length=5)
        assert meta.memory_type == MemoryType.EPISODIC
        assert meta.event_tag is None
        assert meta.outcome is None
        assert meta.related_session_id is None

    def test_full(self) -> None:
        meta = EpisodicMeta(
            role='assistant',
            offset=100,
            length=50,
            event_tag='login_attempt',
            outcome='success',
            related_session_id='sess-42',
        )
        assert meta.event_tag == 'login_attempt'
        assert meta.outcome == 'success'
        assert meta.related_session_id == 'sess-42'

    def test_is_message_meta(self) -> None:
        meta = EpisodicMeta(role='user', offset=0, length=5)
        assert isinstance(meta, MessageMeta)

    def test_satisfies_memory_entry(self) -> None:
        meta = EpisodicMeta(role='user', offset=0, length=5)
        assert isinstance(meta, MemoryEntry)


class TestProceduralMeta:
    """Verify ProceduralMeta subclass."""

    def test_defaults(self) -> None:
        meta = ProceduralMeta(
            role='system', offset=0, length=5
        )
        assert meta.memory_type == MemoryType.PROCEDURAL
        assert meta.workflow_name is None
        assert meta.step_order is None
        assert meta.trigger is None

    def test_full(self) -> None:
        meta = ProceduralMeta(
            role='system',
            offset=0,
            length=100,
            workflow_name='deploy_pipeline',
            step_order=3,
            trigger='on_merge',
        )
        assert meta.workflow_name == 'deploy_pipeline'
        assert meta.step_order == 3
        assert meta.trigger == 'on_merge'

    def test_satisfies_memory_entry(self) -> None:
        meta = ProceduralMeta(
            role='system', offset=0, length=5
        )
        assert isinstance(meta, MemoryEntry)


class TestSemanticMeta:
    """Verify SemanticMeta subclass."""

    def test_defaults(self) -> None:
        meta = SemanticMeta(
            role='system', offset=0, length=5
        )
        assert meta.memory_type == MemoryType.SEMANTIC
        assert meta.category is None
        assert meta.keywords == []
        assert meta.source_episode_id is None

    def test_full(self) -> None:
        meta = SemanticMeta(
            role='system',
            offset=0,
            length=200,
            category='company_policy',
            keywords=['security', 'access'],
            source_episode_id='ep-99',
        )
        assert meta.category == 'company_policy'
        assert meta.keywords == ['security', 'access']
        assert meta.source_episode_id == 'ep-99'

    def test_satisfies_memory_entry(self) -> None:
        meta = SemanticMeta(
            role='system', offset=0, length=5
        )
        assert isinstance(meta, MemoryEntry)
