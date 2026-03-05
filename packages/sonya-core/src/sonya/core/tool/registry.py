"""ToolRegistry — register, look up, and execute tools."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sonya.core.tool._validation import validate_input
from sonya.core.tool.types import Tool, ToolResult


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
    ) -> ToolResult:
        """Execute a single tool by name.

        Args:
            name: The tool name.
            call_id: Provider-assigned tool call id.
            arguments: Dict of arguments or a JSON string.

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

        # Execute
        try:
            result = await tool.fn(**arguments)
            return ToolResult(
                call_id=call_id,
                name=name,
                success=True,
                output=str(result),
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                name=name,
                success=False,
                error=str(e),
            )

    async def execute_many(
        self,
        calls: list[tuple[str, str, dict[str, Any] | str]],
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Args:
            calls: List of (name, call_id, arguments) tuples.

        Returns:
            List of :class:`ToolResult` in the same order.
        """
        tasks = [
            self.execute(name, call_id, args)
            for name, call_id, args in calls
        ]
        return await asyncio.gather(*tasks)

    def schemas(self, provider: str) -> list[dict[str, Any]]:
        """Export all tool schemas for the given provider.

        Args:
            provider: One of ``'anthropic'``, ``'openai'``, ``'gemini'``.

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
        return [formatter(t) for t in self._tools.values()]
