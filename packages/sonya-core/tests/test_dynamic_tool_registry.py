"""Tests for dynamic tool registration: has, unregister, register_many, clear."""

from __future__ import annotations

import pytest

from sonya.core.models.tool import Tool
from sonya.core.models.tool_registry import ToolRegistry


def _make_tool(name: str) -> Tool:
    async def fn() -> str:
        return name

    return Tool(
        name=name,
        description='test tool',
        fn=fn,
        schema={'type': 'object', 'properties': {}},
    )


# --- has() ---

def test_has_existing_tool() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('alpha'))
    assert registry.has('alpha') is True


def test_has_missing_tool() -> None:
    registry = ToolRegistry()
    assert registry.has('ghost') is False


def test_has_after_unregister() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('beta'))
    registry.unregister('beta')
    assert registry.has('beta') is False


# --- unregister() ---

def test_unregister_removes_tool() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('gamma'))
    registry.unregister('gamma')
    assert registry.get('gamma') is None
    assert len(registry.tools) == 0


def test_unregister_unknown_tool_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match='gamma'):
        registry.unregister('gamma')


def test_unregister_allows_reregistration() -> None:
    registry = ToolRegistry()
    tool = _make_tool('delta')
    registry.register(tool)
    registry.unregister('delta')
    # Should not raise after removal
    registry.register(tool)
    assert registry.has('delta') is True


def test_unregister_middle_preserves_others() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('a'))
    registry.register(_make_tool('b'))
    registry.register(_make_tool('c'))
    registry.unregister('b')
    names = [t.name for t in registry.tools]
    assert names == ['a', 'c']


# --- register_many() ---

def test_register_many_adds_all_tools() -> None:
    registry = ToolRegistry()
    tools = [_make_tool('x'), _make_tool('y'), _make_tool('z')]
    registry.register_many(tools)
    assert registry.has('x')
    assert registry.has('y')
    assert registry.has('z')
    assert len(registry.tools) == 3


def test_register_many_raises_on_duplicate() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('dup'))
    with pytest.raises(ValueError, match='dup'):
        registry.register_many([_make_tool('ok'), _make_tool('dup')])


def test_register_many_empty_list_is_noop() -> None:
    registry = ToolRegistry()
    registry.register_many([])
    assert registry.tools == []


# --- clear() ---

def test_clear_removes_all_tools() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('p'))
    registry.register(_make_tool('q'))
    registry.clear()
    assert registry.tools == []


def test_clear_allows_reregistration() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('r'))
    registry.clear()
    registry.register(_make_tool('r'))
    assert registry.has('r') is True


def test_clear_on_empty_registry_is_noop() -> None:
    registry = ToolRegistry()
    registry.clear()
    assert registry.tools == []


# --- interaction with schemas() ---

def test_schemas_reflect_unregister() -> None:
    registry = ToolRegistry()
    registry.register(_make_tool('tool_a'))
    registry.register(_make_tool('tool_b'))
    registry.unregister('tool_a')
    schemas = registry.schemas('anthropic')
    names = [s['name'] for s in schemas]
    assert 'tool_a' not in names
    assert 'tool_b' in names


def test_schemas_reflect_register_many() -> None:
    registry = ToolRegistry()
    registry.register_many([_make_tool('m1'), _make_tool('m2')])
    schemas = registry.schemas('openai')
    names = [s['function']['name'] for s in schemas]
    assert 'm1' in names
    assert 'm2' in names
