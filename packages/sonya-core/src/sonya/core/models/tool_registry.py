"""ToolRegistry — register, look up, and execute tools."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, get_type_hints

from sonya.core.utils.validation import validate_input
from .tool import Tool, ToolResult

if TYPE_CHECKING:
    from sonya.core.utils.tool_context import ToolContext

_log = logging.getLogger('sonya.tool_registry')


def _find_context_params(fn: Any) -> list[str]:
    """Return parameter names typed as ToolContext in *fn*'s signature.

    Uses a name+module check to avoid a circular import.
    Result is computed fresh each call; callers may cache it if needed.
    """
    try:
        hints = {}
        try:
            hints = get_type_hints(fn)
        except Exception:
            hints = getattr(fn, '__annotations__', {})

        result = []
        for name, annotation in hints.items():
            if name == 'return':
                continue
            cls = annotation if isinstance(annotation, type) else None
            if (
                cls is not None
                and cls.__name__ == 'ToolContext'
                and cls.__module__.startswith('sonya.core')
            ):
                result.append(name)
        return result
    except Exception:
        return []


class ToolRegistry:
    """Central registry for :class:`Tool` instances.

    Supports registration, lookup, single/parallel execution,
    and schema export per provider format.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Raises ValueError on duplicate names."""
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered"
            )
        self._tools[tool.name] = tool

    def register_many(self, tools: list[Tool]) -> None:
        """Register multiple tools at once.

        Args:
            tools: Tools to register in order.

        Raises:
            ValueError: If any tool name is already registered.
        """
        for t in tools:
            self.register(t)

    def unregister(self, name: str) -> None:
        """Remove a registered tool by name.

        Args:
            name: The name of the tool to remove.

        Raises:
            ValueError: If no tool with *name* is registered.
        """
        if name not in self._tools:
            raise ValueError(
                f"Tool '{name}' is not registered"
            )
        del self._tools[name]

    def has(self, name: str) -> bool:
        """Return True if a tool with *name* is registered."""
        return name in self._tools

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()

    def get(self, name: str) -> Tool | None:
        """Return the tool with *name*, or None if not found."""
        return self._tools.get(name)

    @property
    def tools(self) -> list[Tool]:
        """Return all registered tools in insertion order."""
        return list(self._tools.values())

    async def execute(
        self,
        name: str,
        call_id: str,
        arguments: dict[str, Any] | str,
        *,
        context: 'ToolContext | None' = None,
    ) -> ToolResult:
        """Execute a single tool by name.

        If the tool function declares any parameter typed as
        :class:`~sonya.core.utils.tool_context.ToolContext`, that
        parameter is injected with *context* at call time and must
        not appear in *arguments*.

        Args:
            name: The tool name.
            call_id: Provider-assigned tool call id.
            arguments: Dict of arguments or a JSON string.
            context: Optional :class:`ToolContext` to inject into
                tool functions that accept it.

        Returns:
            A :class:`ToolResult` with the output or error.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                call_id=call_id,
                name=name,
                success=False,
                error=f"Unknown tool: '{name}'",
            )

        # Parse JSON string arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as e:
                return ToolResult(
                    call_id=call_id,
                    name=name,
                    success=False,
                    error=f'Invalid JSON arguments: {e}',
                )

        # Validate
        errors = validate_input(arguments, tool.schema)
        if errors:
            return ToolResult(
                call_id=call_id,
                name=name,
                success=False,
                error='; '.join(errors),
            )

        # Inject ToolContext parameters if context is provided.
        # arguments is guaranteed to be a dict at this point (any
        # JSON string was parsed above); cast away the union.
        _args: dict[str, Any] = arguments  # pyright: ignore[reportAssignmentType]
        if context is not None:
            for param_name in _find_context_params(tool.fn):
                _args[param_name] = context

        # Execute
        # Intentional broad catch: tool.fn is user-supplied code that
        # may raise any exception. We sandbox the failure into a
        # ToolResult rather than propagating, so the agent loop can
        # continue. The warning log preserves debuggability.
        try:
            result = await tool.fn(**_args)
            return ToolResult(
                call_id=call_id,
                name=name,
                success=True,
                output=str(result),
            )
        except Exception as e:
            _log.warning(
                'Tool %r raised %s: %s',
                name,
                type(e).__name__,
                e,
            )
            return ToolResult(
                call_id=call_id,
                name=name,
                success=False,
                error=str(e),
            )

    async def execute_many(
        self,
        calls: list[
            tuple[str, str, dict[str, Any] | str]
        ],
        max_concurrency: int | None = None,
        *,
        context: 'ToolContext | None' = None,
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        When *max_concurrency* is given, at most that many tools
        run simultaneously (bounded via :class:`asyncio.Semaphore`).
        Pass ``None`` (default) for unlimited parallelism.

        Args:
            calls: List of (name, call_id, arguments) tuples.
            max_concurrency: Maximum simultaneous executions,
                or None for unlimited.
            context: Optional :class:`ToolContext` forwarded to
                each :meth:`execute` call.

        Returns:
            List of :class:`ToolResult` in the same order.
        """
        if max_concurrency is None:
            tasks = [
                self.execute(name, call_id, args, context=context)
                for name, call_id, args in calls
            ]
            return list(await asyncio.gather(*tasks))

        sem = asyncio.Semaphore(max_concurrency)

        async def _limited(
            name: str,
            call_id: str,
            args: dict[str, Any] | str,
        ) -> ToolResult:
            async with sem:
                return await self.execute(
                    name, call_id, args, context=context
                )

        tasks = [
            _limited(name, call_id, args)
            for name, call_id, args in calls
        ]
        return list(await asyncio.gather(*tasks))

    async def execute_sequential(
        self,
        calls: list[
            tuple[str, str, dict[str, Any] | str]
        ],
        *,
        context: 'ToolContext | None' = None,
    ) -> list[ToolResult]:
        """Execute multiple tool calls one at a time in order.

        Args:
            calls: List of (name, call_id, arguments) tuples.
            context: Optional :class:`ToolContext` forwarded to
                each :meth:`execute` call.

        Returns:
            List of :class:`ToolResult` in the same order.
        """
        results: list[ToolResult] = []
        for name, call_id, args in calls:
            results.append(
                await self.execute(
                    name, call_id, args, context=context
                )
            )
        return results

    def schemas(
        self, provider: str
    ) -> list[dict[str, Any]]:
        """Export all tool schemas for the given provider.

        Args:
            provider: One of ``'anthropic'``, ``'openai'``,
                ``'gemini'``.

        Returns:
            List of provider-formatted tool schema dicts.

        Raises:
            ValueError: If the provider is not supported.
        """
        _format_map = {
            'anthropic': lambda t: t.to_anthropic_schema(),
            'openai': lambda t: t.to_openai_schema(),
            'gemini': lambda t: t.to_gemini_schema(),
        }
        formatter = _format_map.get(provider)
        if formatter is None:
            raise ValueError(
                f"Unsupported provider: '{provider}'. "
                f"Choose from: {list(_format_map.keys())}"
            )
        return [
            formatter(t) for t in self._tools.values()
        ]
