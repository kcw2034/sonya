"""Tests for automatic ToolContext injection into tool functions."""

from __future__ import annotations


import pytest

from sonya.core.models.tool import Tool
from sonya.core.models.tool_registry import ToolRegistry
from sonya.core.parsers.schema_parser import function_to_schema
from sonya.core.utils.tool_context import ToolContext
from sonya.core.utils.decorator import tool


# --- Schema generation: ToolContext params excluded ---

def test_schema_excludes_tool_context_param() -> None:
    async def fn(query: str, context: ToolContext) -> str:
        return query

    schema = function_to_schema(fn)
    assert 'context' not in schema['properties']
    assert 'query' in schema['properties']


def test_schema_excludes_tool_context_from_required() -> None:
    async def fn(query: str, context: ToolContext) -> str:
        return query

    schema = function_to_schema(fn)
    required = schema.get('required', [])
    assert 'context' not in required
    assert 'query' in required


def test_schema_without_context_param_unchanged() -> None:
    async def fn(x: str, y: int) -> str:
        return x

    schema = function_to_schema(fn)
    assert 'x' in schema['properties']
    assert 'y' in schema['properties']


def test_schema_tool_context_only_param_yields_empty_properties() -> None:
    async def fn(context: ToolContext) -> str:
        return 'ok'

    schema = function_to_schema(fn)
    assert schema['properties'] == {}
    assert 'required' not in schema


# --- ToolRegistry: context injection ---

@pytest.mark.asyncio
async def test_registry_injects_context_into_tool_fn() -> None:
    received: list[ToolContext] = []

    async def fn(msg: str, context: ToolContext) -> str:
        received.append(context)
        return msg

    t = Tool(
        name='fn',
        description='test',
        fn=fn,
        schema=function_to_schema(fn),
    )
    registry = ToolRegistry()
    registry.register(t)

    ctx = ToolContext()
    result = await registry.execute('fn', 'c1', {'msg': 'hi'}, context=ctx)
    assert result.success is True
    assert len(received) == 1
    assert received[0] is ctx


@pytest.mark.asyncio
async def test_registry_skips_injection_when_no_context_param() -> None:
    called_with: list[dict] = []

    async def fn(x: str) -> str:
        called_with.append({'x': x})
        return x

    t = Tool(
        name='fn',
        description='test',
        fn=fn,
        schema=function_to_schema(fn),
    )
    registry = ToolRegistry()
    registry.register(t)

    ctx = ToolContext()
    result = await registry.execute('fn', 'c1', {'x': 'hello'}, context=ctx)
    assert result.success is True
    assert called_with == [{'x': 'hello'}]


@pytest.mark.asyncio
async def test_registry_context_defaults_to_none() -> None:
    """execute() with no context arg must not break existing callers."""
    async def fn(x: str) -> str:
        return x

    t = Tool(
        name='fn',
        description='test',
        fn=fn,
        schema=function_to_schema(fn),
    )
    registry = ToolRegistry()
    registry.register(t)

    result = await registry.execute('fn', 'c1', {'x': 'hi'})
    assert result.success is True


@pytest.mark.asyncio
async def test_registry_execute_many_threads_context() -> None:
    received: list[ToolContext] = []

    async def fn(x: str, context: ToolContext) -> str:
        received.append(context)
        return x

    t = Tool(
        name='fn', description='t', fn=fn,
        schema=function_to_schema(fn),
    )
    registry = ToolRegistry()
    registry.register(t)

    ctx = ToolContext()
    results = await registry.execute_many(
        [('fn', 'c1', {'x': 'a'}), ('fn', 'c2', {'x': 'b'})],
        context=ctx,
    )
    assert all(r.success for r in results)
    assert len(received) == 2
    assert all(c is ctx for c in received)


@pytest.mark.asyncio
async def test_registry_execute_sequential_threads_context() -> None:
    received: list[ToolContext] = []

    async def fn(x: str, context: ToolContext) -> str:
        received.append(context)
        return x

    t = Tool(
        name='fn', description='t', fn=fn,
        schema=function_to_schema(fn),
    )
    registry = ToolRegistry()
    registry.register(t)

    ctx = ToolContext()
    results = await registry.execute_sequential(
        [('fn', 'c1', {'x': 'a'}), ('fn', 'c2', {'x': 'b'})],
        context=ctx,
    )
    assert all(r.success for r in results)
    assert len(received) == 2


# --- @tool decorator + context injection ---

@pytest.mark.asyncio
async def test_tool_decorator_with_context_param_excludes_from_schema() -> None:
    @tool()
    async def my_tool(query: str, context: ToolContext) -> str:
        """A tool that uses context."""
        return f'got {query}'

    assert 'context' not in my_tool.schema['properties']
    assert 'query' in my_tool.schema['properties']


@pytest.mark.asyncio
async def test_full_round_trip_tool_with_context() -> None:
    """Tool decorated with @tool, registered, and executed with context."""
    ctx_received: list[ToolContext] = []

    @tool()
    async def searcher(query: str, context: ToolContext) -> str:
        """Search tool that stores in context."""
        context.set('last_query', query)
        ctx_received.append(context)
        return f'results for {query}'

    registry = ToolRegistry()
    registry.register(searcher)

    ctx = ToolContext()
    result = await registry.execute(
        'searcher', 'c1', {'query': 'hello'}, context=ctx
    )
    assert result.success is True
    assert 'results for hello' in result.output
    assert ctx.get('last_query') == 'hello'
    assert len(ctx_received) == 1
