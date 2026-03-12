"""Bidirectional tool converters between sonya and LangChain."""

from __future__ import annotations

import asyncio
import functools
from typing import Any

from sonya.core import Tool

from sonya.extension.schemas.types import _check_langchain


def to_langchain_tool(sonya_tool: Tool) -> Any:
    """Convert a sonya Tool to a LangChain StructuredTool.

    Args:
        sonya_tool: A sonya-core Tool instance.

    Returns:
        A LangChain StructuredTool wrapping the sonya tool.
    """
    _check_langchain()
    from langchain_core.tools import StructuredTool

    fn = sonya_tool.fn

    if asyncio.iscoroutinefunction(fn):
        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return asyncio.run(fn(*args, **kwargs))

        return StructuredTool.from_function(
            func=_sync_wrapper,
            coroutine=fn,
            name=sonya_tool.name,
            description=sonya_tool.description,
        )

    return StructuredTool.from_function(
        func=fn,
        name=sonya_tool.name,
        description=sonya_tool.description,
    )


def to_sonya_tool(langchain_tool: Any) -> Tool:
    """Convert a LangChain BaseTool to a sonya Tool.

    Args:
        langchain_tool: A LangChain BaseTool instance.

    Returns:
        A sonya-core Tool wrapping the LangChain tool.
    """
    _check_langchain()
    from langchain_core.tools import BaseTool

    if not isinstance(langchain_tool, BaseTool):
        raise TypeError(
            f'Expected a LangChain BaseTool, '
            f'got {type(langchain_tool).__name__}'
        )

    schema = _build_schema(langchain_tool)

    async def _async_invoke(**kwargs: Any) -> str:
        if hasattr(langchain_tool, '_arun'):
            try:
                result = await langchain_tool.ainvoke(kwargs)
                return str(result)
            except NotImplementedError:
                pass

        result = langchain_tool.invoke(kwargs)
        return str(result)

    return Tool(
        name=langchain_tool.name,
        description=langchain_tool.description or '',
        fn=_async_invoke,
        schema=schema,
    )


def _build_schema(langchain_tool: Any) -> dict[str, Any]:
    """Build JSON Schema from a LangChain tool's args_schema.

    Args:
        langchain_tool: A LangChain BaseTool instance.

    Returns:
        A JSON Schema dict for the tool parameters.
    """
    if hasattr(langchain_tool, 'args_schema') \
            and langchain_tool.args_schema is not None:
        raw = langchain_tool.args_schema.model_json_schema()
        return {
            'type': 'object',
            'properties': raw.get('properties', {}),
            'required': raw.get('required', []),
        }

    return {'type': 'object', 'properties': {}}
