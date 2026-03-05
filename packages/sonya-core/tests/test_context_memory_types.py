"""Tests for context memory types."""

from __future__ import annotations

import pytest

from sonya.core.context.memory.types import NormalizedMessage


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
