"""@tool decorator for creating Tool instances from functions."""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable

from sonya.core.parsers.schema_parser import function_to_schema
from sonya.core.models.tool import Tool


def tool(
    name: str | None = None,
    description: str | None = None,
    requires_approval: bool = False,
) -> Callable[..., Tool]:
    """Decorator that converts a function into a :class:`Tool`.

    Automatically generates a JSON Schema from type hints and wraps
    sync functions as async.

    Args:
        name: Override the tool name (defaults to ``fn.__name__``).
        description: Override the description (defaults to docstring).
        requires_approval: If True, the AgentRuntime will call
            ``AgentCallback.on_approval_request`` before executing
            this tool. Execution is skipped if any callback returns
            False.

    Returns:
        A decorator that produces a ``Tool`` instance.

    Example::

        @tool(description='Add two numbers')
        def add(a: int, b: int) -> int:
            return a + b
    """

    def _decorator(fn: Callable[..., Any]) -> Tool:
        _name = name or fn.__name__
        _description = (
            description or (fn.__doc__ or '').strip()
        )
        _schema = function_to_schema(fn)

        # Wrap sync functions as async
        if not inspect.iscoroutinefunction(fn):
            _original = fn

            @functools.wraps(_original)
            async def _async_fn(
                *args: Any, **kwargs: Any
            ) -> Any:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None,
                    functools.partial(
                        _original, *args, **kwargs
                    ),
                )

            _fn = _async_fn
        else:
            _fn = fn

        return Tool(
            name=_name,
            description=_description,
            fn=_fn,
            schema=_schema,
            requires_approval=requires_approval,
        )

    return _decorator
