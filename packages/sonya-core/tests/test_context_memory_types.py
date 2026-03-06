"""Tests for context memory types."""

from __future__ import annotations

import pytest

from typing import Any

from sonya.core.schemas.memory import (
    MemoryEntry,
    MemoryPipeline,
    MemoryType,
    NormalizedMessage,
)


class TestNormalizedMessage:
    """Verify NormalizedMessage creation and immutability."""

    def test_creation_defaults(self) -> None:
        msg = NormalizedMessage(role='user', content='hello')
        assert msg.role == 'user'
        assert msg.content == 'hello'
        assert msg.tool_calls == []
        assert msg.tool_results == []
        assert msg.metadata == {}

    def test_creation_full(self) -> None:
        msg = NormalizedMessage(
            role='assistant',
            content='hi',
            tool_calls=[{'id': 'tc1', 'name': 'add'}],
            tool_results=[{'id': 'tc1', 'output': '3'}],
            metadata={
                'agent_name': 'calc',
                'provider': 'openai',
            },
        )
        assert msg.role == 'assistant'
        assert len(msg.tool_calls) == 1
        assert msg.metadata['provider'] == 'openai'

    def test_frozen(self) -> None:
        msg = NormalizedMessage(role='user', content='hi')
        with pytest.raises(AttributeError):
            msg.role = 'system'  # type: ignore[misc]

    def test_slots(self) -> None:
        msg = NormalizedMessage(role='user', content='hi')
        assert not hasattr(msg, '__dict__')


class TestMemoryPipelineProtocol:
    """Verify MemoryPipeline Protocol compliance."""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(MemoryPipeline, type)

    def test_conforming_class_isinstance(self) -> None:
        class FakePipeline:
            def normalize(
                self,
                history: list[dict[str, Any]],
                source_provider: str,
            ) -> list[NormalizedMessage]:
                return []

            def reconstruct(
                self,
                messages: list[NormalizedMessage],
                target_provider: str,
            ) -> list[dict[str, Any]]:
                return []

        assert isinstance(FakePipeline(), MemoryPipeline)

    def test_non_conforming_class(self) -> None:
        class NotAPipeline:
            pass

        assert not isinstance(NotAPipeline(), MemoryPipeline)


class TestMemoryType:
    """Verify MemoryType enum values."""

    def test_enum_values(self) -> None:
        assert MemoryType.EPISODIC.value == 'episodic'
        assert MemoryType.PROCEDURAL.value == 'procedural'
        assert MemoryType.SEMANTIC.value == 'semantic'

    def test_enum_count(self) -> None:
        assert len(MemoryType) == 3


class TestMemoryEntryProtocol:
    """Verify MemoryEntry Protocol compliance."""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(MemoryEntry, type)

    def test_conforming_class(self) -> None:
        class FakeEntry:
            @property
            def memory_type(self) -> MemoryType:
                return MemoryType.EPISODIC

            @property
            def content(self) -> str:
                return 'test'

            @property
            def timestamp(self) -> float:
                return 0.0

        assert isinstance(FakeEntry(), MemoryEntry)

    def test_non_conforming_class(self) -> None:
        class NotAnEntry:
            pass

        assert not isinstance(NotAnEntry(), MemoryEntry)
