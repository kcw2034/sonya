"""Tests for ToolRegistry execution and error handling."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from sonya.core.models.tool import Tool
from sonya.core.models.tool_registry import ToolRegistry


def _make_tool(name: str, fn: Any) -> Tool:
    return Tool(
        name=name,
        description='test',
        fn=fn,
        schema={
            'type': 'object',
            'properties': {
                'x': {'type': 'string'},
            },
            'required': ['x'],
        },
    )


@pytest.mark.asyncio
async def test_execute_success() -> None:
    async def greet(x: str) -> str:
        return f'hello {x}'

    registry = ToolRegistry()
    registry.register(_make_tool('greet', greet))

    result = await registry.execute('greet', 'call1', {'x': 'world'})
    assert result.success is True
    assert result.output == 'hello world'
    assert result.call_id == 'call1'


@pytest.mark.asyncio
async def test_execute_unknown_tool() -> None:
    registry = ToolRegistry()
    result = await registry.execute('missing', 'call1', {})
    assert result.success is False
    assert 'Unknown tool' in (result.error or '')


@pytest.mark.asyncio
async def test_execute_invalid_json_args() -> None:
    async def fn(x: str) -> str:
        return x

    registry = ToolRegistry()
    registry.register(_make_tool('fn', fn))

    result = await registry.execute('fn', 'call1', '{bad json}')
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_execute_tool_exception_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When a tool raises, a WARNING must be logged with the error detail."""
    async def broken(x: str) -> str:
        raise ValueError('tool exploded')

    registry = ToolRegistry()
    registry.register(_make_tool('broken', broken))

    with caplog.at_level(logging.WARNING, logger='sonya.tool_registry'):
        result = await registry.execute('broken', 'call1', {'x': 'hi'})

    assert result.success is False
    assert 'tool exploded' in (result.error or '')
    # A WARNING must have been emitted for the failure
    warning_messages = [
        r.message for r in caplog.records
        if r.levelno == logging.WARNING
    ]
    assert any('tool exploded' in m for m in warning_messages), (
        f'Expected WARNING containing "tool exploded", got: {warning_messages}'
    )


@pytest.mark.asyncio
async def test_execute_many_parallel() -> None:
    results_order: list[str] = []

    async def task_a(x: str) -> str:
        results_order.append('a')
        return f'a:{x}'

    async def task_b(x: str) -> str:
        results_order.append('b')
        return f'b:{x}'

    registry = ToolRegistry()
    registry.register(_make_tool('task_a', task_a))
    registry.register(_make_tool('task_b', task_b))

    results = await registry.execute_many([
        ('task_a', 'c1', {'x': '1'}),
        ('task_b', 'c2', {'x': '2'}),
    ])

    assert len(results) == 2
    assert results[0].output == 'a:1'
    assert results[1].output == 'b:2'
