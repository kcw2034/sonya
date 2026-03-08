"""Tests for BinContextEngine memory_type support."""

from __future__ import annotations

import pytest

from sonya.core.schemas.memory import MemoryType
from sonya.pack.client.engine import BinContextEngine
from sonya.pack.schemas.schema import (
    EpisodicMeta,
    ProceduralMeta,
    SemanticMeta,
)


@pytest.fixture
def engine(tmp_path):
    return BinContextEngine(tmp_path)


class TestAddMessageMemoryType:
    """Verify add_message supports memory_type."""

    def test_default_episodic(self, engine) -> None:
        meta = engine.add_message('s1', 'user', 'hello')
        assert meta.memory_type == MemoryType.EPISODIC
        assert isinstance(meta, EpisodicMeta)

    def test_procedural(self, engine) -> None:
        meta = engine.add_message(
            's1', 'system', 'step 1: do X',
            memory_type=MemoryType.PROCEDURAL,
            workflow_name='deploy',
            step_order=1,
        )
        assert meta.memory_type == MemoryType.PROCEDURAL
        assert isinstance(meta, ProceduralMeta)
        assert meta.workflow_name == 'deploy'

    def test_semantic(self, engine) -> None:
        meta = engine.add_message(
            's1', 'system', 'company uses Python 3.11',
            memory_type=MemoryType.SEMANTIC,
            category='tech_stack',
            keywords=['python', 'version'],
        )
        assert meta.memory_type == MemoryType.SEMANTIC
        assert isinstance(meta, SemanticMeta)
        assert meta.keywords == ['python', 'version']


class TestBuildContextFilter:
    """Verify build_context filters by memory_type."""

    def test_filter_episodic_only(self, engine) -> None:
        engine.add_message('s1', 'user', 'event A')
        engine.add_message(
            's1', 'system', 'rule X',
            memory_type=MemoryType.PROCEDURAL,
        )
        engine.add_message('s1', 'assistant', 'event B')

        result = engine.build_context(
            's1', memory_type=MemoryType.EPISODIC
        )
        assert len(result) == 2
        assert result[0]['content'] == 'event A'
        assert result[1]['content'] == 'event B'

    def test_filter_none_returns_all(self, engine) -> None:
        engine.add_message('s1', 'user', 'msg1')
        engine.add_message(
            's1', 'system', 'proc1',
            memory_type=MemoryType.PROCEDURAL,
        )
        result = engine.build_context('s1')
        assert len(result) == 2

    def test_combined_filter_and_last_n(self, engine) -> None:
        for i in range(5):
            engine.add_message('s1', 'user', f'event {i}')
        engine.add_message(
            's1', 'system', 'knowledge',
            memory_type=MemoryType.SEMANTIC,
        )
        result = engine.build_context(
            's1',
            memory_type=MemoryType.EPISODIC,
            last_n_turns=2,
        )
        assert len(result) == 2
        assert result[0]['content'] == 'event 3'
        assert result[1]['content'] == 'event 4'


class TestMetadataPersistence:
    """Verify memory_type survives save/load cycle."""

    def test_round_trip(self, tmp_path) -> None:
        engine1 = BinContextEngine(tmp_path)
        engine1.add_message('s1', 'user', 'hello')
        engine1.add_message(
            's1', 'system', 'rule',
            memory_type=MemoryType.PROCEDURAL,
            workflow_name='onboard',
        )
        engine1.add_message(
            's1', 'system', 'fact',
            memory_type=MemoryType.SEMANTIC,
            category='hr',
        )

        # Reload from disk
        engine2 = BinContextEngine(tmp_path)
        session = engine2.get_session('s1')
        assert len(session.messages) == 3
        assert session.messages[0].memory_type == MemoryType.EPISODIC
        assert session.messages[1].memory_type == MemoryType.PROCEDURAL
        assert isinstance(session.messages[1], ProceduralMeta)
        assert session.messages[1].workflow_name == 'onboard'
        assert session.messages[2].memory_type == MemoryType.SEMANTIC
        assert isinstance(session.messages[2], SemanticMeta)
        assert session.messages[2].category == 'hr'
