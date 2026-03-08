"""Tests for bidirectional tool conversion."""

from __future__ import annotations

import asyncio

import pytest

from sonya.core import Tool

from sonya.extension import to_langchain_tool, to_sonya_tool


class TestToLangchainTool:
    """Tests for sonya Tool → LangChain StructuredTool."""

    def test_sync_tool_conversion(self) -> None:
        """Sync sonya tool converts to LangChain tool."""
        def add(a: int, b: int) -> int:
            return a + b

        sonya_tool = Tool(
            name='add',
            description='Add two numbers',
            fn=add,
            schema={
                'type': 'object',
                'properties': {
                    'a': {'type': 'integer'},
                    'b': {'type': 'integer'},
                },
                'required': ['a', 'b'],
            },
        )

        lc_tool = to_langchain_tool(sonya_tool)

        assert lc_tool.name == 'add'
        assert lc_tool.description == 'Add two numbers'
        result = lc_tool.invoke({'a': 2, 'b': 3})
        assert result == 5

    def test_async_tool_conversion(self) -> None:
        """Async sonya tool converts to LangChain tool."""
        async def multiply(x: int, y: int) -> int:
            return x * y

        sonya_tool = Tool(
            name='multiply',
            description='Multiply two numbers',
            fn=multiply,
            schema={
                'type': 'object',
                'properties': {
                    'x': {'type': 'integer'},
                    'y': {'type': 'integer'},
                },
                'required': ['x', 'y'],
            },
        )

        lc_tool = to_langchain_tool(sonya_tool)

        assert lc_tool.name == 'multiply'
        assert lc_tool.coroutine is not None
        result = lc_tool.invoke({'x': 3, 'y': 4})
        assert result == 12


class TestToSonyaTool:
    """Tests for LangChain BaseTool → sonya Tool."""

    def test_structured_tool_conversion(self) -> None:
        """LangChain StructuredTool converts to sonya tool."""
        from langchain_core.tools import StructuredTool

        def greet(name: str) -> str:
            return f'Hello, {name}!'

        lc_tool = StructuredTool.from_function(
            func=greet,
            name='greet',
            description='Greet someone',
        )

        sonya_tool = to_sonya_tool(lc_tool)

        assert sonya_tool.name == 'greet'
        assert sonya_tool.description == 'Greet someone'
        assert 'name' in sonya_tool.schema['properties']

        result = asyncio.run(
            sonya_tool.fn(name='World')
        )
        assert result == 'Hello, World!'

    def test_invalid_type_raises(self) -> None:
        """Non-BaseTool input raises TypeError."""
        with pytest.raises(TypeError, match='BaseTool'):
            to_sonya_tool('not a tool')
