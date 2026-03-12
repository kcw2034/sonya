"""Tests for tool_calls/tool_results preservation in BridgeStore."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sonya.pipeline.stores.bridge_store import BridgeStore
from sonya.core.schemas.memory import NormalizedMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge(stored: list[dict[str, Any]] | None = None) -> Any:
    """Return a fake ContextBridge with controllable load_context."""
    bridge = MagicMock()
    bridge.load_context.return_value = stored or []
    bridge.save_messages = MagicMock()
    return bridge


# ---------------------------------------------------------------------------
# Save preserves tool_calls
# ---------------------------------------------------------------------------

def test_save_includes_tool_calls() -> None:
    """BridgeStore.save() includes tool_calls in persisted dict."""
    bridge = _make_bridge()
    store = BridgeStore(bridge)
    msgs = [
        NormalizedMessage(
            role='assistant',
            content='searching...',
            tool_calls=[
                {'id': 'tc_1', 'name': 'search', 'arguments': {'q': 'py'}}
            ],
        )
    ]
    store.save('s1', msgs)
    saved = bridge.save_messages.call_args[0][1]
    assert saved[0]['tool_calls'] == msgs[0].tool_calls


def test_save_includes_tool_results() -> None:
    """BridgeStore.save() includes tool_results in persisted dict."""
    bridge = _make_bridge()
    store = BridgeStore(bridge)
    msgs = [
        NormalizedMessage(
            role='user',
            content='',
            tool_results=[
                {'call_id': 'tc_1', 'output': 'result', 'name': 'search'}
            ],
        )
    ]
    store.save('s1', msgs)
    saved = bridge.save_messages.call_args[0][1]
    assert saved[0]['tool_results'] == msgs[0].tool_results


# ---------------------------------------------------------------------------
# Load restores tool_calls
# ---------------------------------------------------------------------------

def test_load_restores_tool_calls() -> None:
    """BridgeStore.load() reconstructs NormalizedMessage with tool_calls."""
    tool_calls = [
        {'id': 'tc_2', 'name': 'calc', 'arguments': {'x': 7}}
    ]
    bridge = _make_bridge([
        {
            'role': 'assistant',
            'content': 'calc result',
            'tool_calls': tool_calls,
            'tool_results': [],
        }
    ])
    store = BridgeStore(bridge)
    msgs = store.load('s1')
    assert len(msgs) == 1
    assert msgs[0].tool_calls == tool_calls


def test_load_restores_tool_results() -> None:
    """BridgeStore.load() reconstructs NormalizedMessage with tool_results."""
    tool_results = [
        {'call_id': 'tc_2', 'output': '42', 'name': 'calc'}
    ]
    bridge = _make_bridge([
        {
            'role': 'user',
            'content': '',
            'tool_calls': [],
            'tool_results': tool_results,
        }
    ])
    store = BridgeStore(bridge)
    msgs = store.load('s1')
    assert msgs[0].tool_results == tool_results


# ---------------------------------------------------------------------------
# Backward-compatible: old records without tool_calls key
# ---------------------------------------------------------------------------

def test_load_old_records_without_tool_calls() -> None:
    """Old records without tool_calls key load with empty lists."""
    bridge = _make_bridge([
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ])
    store = BridgeStore(bridge)
    msgs = store.load('s1')
    for msg in msgs:
        assert msg.tool_calls == []
        assert msg.tool_results == []
