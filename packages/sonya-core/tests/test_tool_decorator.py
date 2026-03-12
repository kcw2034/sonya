"""Tests for @tool decorator."""

from __future__ import annotations


import pytest

from sonya.core.utils.decorator import tool
from sonya.core.models.tool import Tool


def test_sync_function_wrapped_as_tool() -> None:
    @tool(description='Add two numbers')
    def add(a: int, b: int) -> int:
        return a + b

    assert isinstance(add, Tool)
    assert add.name == 'add'
    assert add.description == 'Add two numbers'
    assert 'a' in add.schema['properties']
    assert 'b' in add.schema['properties']


def test_async_function_wrapped_as_tool() -> None:
    @tool(description='Async greeting')
    async def greet(name: str) -> str:
        return f'Hello, {name}!'

    assert isinstance(greet, Tool)
    assert greet.name == 'greet'


def test_custom_name() -> None:
    @tool(name='my_tool', description='A custom tool')
    def something(x: int) -> int:
        return x

    assert something.name == 'my_tool'


def test_docstring_as_description() -> None:
    @tool()
    def documented(x: int) -> int:
        """This is the docstring."""
        return x

    assert documented.description == 'This is the docstring.'


@pytest.mark.asyncio
async def test_sync_tool_is_callable_async() -> None:
    @tool(description='Multiply')
    def multiply(a: int, b: int) -> int:
        return a * b

    result = await multiply.fn(a=3, b=4)
    assert result == 12


@pytest.mark.asyncio
async def test_async_tool_is_callable() -> None:
    @tool(description='Async add')
    async def async_add(a: int, b: int) -> int:
        return a + b

    result = await async_add.fn(a=5, b=7)
    assert result == 12


def test_schema_has_required_fields() -> None:
    @tool(description='Test')
    def fn(required_arg: str, optional_arg: int = 0) -> None:
        ...

    assert fn.schema['required'] == ['required_arg']


def test_tool_provider_schemas() -> None:
    @tool(description='Test tool')
    def test_fn(x: int) -> int:
        return x

    anthropic = test_fn.to_anthropic_schema()
    assert anthropic['name'] == 'test_fn'
    assert 'input_schema' in anthropic

    openai = test_fn.to_openai_schema()
    assert openai['type'] == 'function'
    assert openai['function']['name'] == 'test_fn'

    gemini = test_fn.to_gemini_schema()
    assert gemini['name'] == 'test_fn'
    assert 'parameters' in gemini
