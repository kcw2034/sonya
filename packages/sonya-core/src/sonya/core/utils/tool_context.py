"""ToolContext — lightweight run-scoped key-value store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sonya.core.models.tool import Tool
    from sonya.core.models.tool_registry import ToolRegistry


class ToolContext:
    """Run-scoped key-value store shared across tool executions.

    Provides a simple mutable namespace that tools can use to share
    state within a single agent run. When bound to a
    :class:`~sonya.core.models.tool_registry.ToolRegistry` (via the
    *registry* constructor parameter), exposes :meth:`add_tool` and
    :meth:`remove_tool` for dynamic tool registration mid-run.

    Example::

        ctx = ToolContext()
        ctx.set('user_id', 42)
        assert ctx.get('user_id') == 42
    """

    def __init__(
        self,
        registry: 'ToolRegistry | None' = None,
    ) -> None:
        self._store: dict[str, Any] = {}
        self._registry: 'ToolRegistry | None' = registry

    def set(self, key: str, value: Any) -> None:
        """Store a value under *key*."""
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the value for *key*, or *default* if absent."""
        return self._store.get(key, default)

    def has(self, key: str) -> bool:
        """Return True if *key* exists in the store."""
        return key in self._store

    def keys(self) -> list[str]:
        """Return all keys currently stored."""
        return list(self._store.keys())

    def summary(self) -> dict[str, Any]:
        """Return a shallow copy of the entire store."""
        return dict(self._store)

    def clear(self) -> None:
        """Remove all entries from the store."""
        self._store.clear()

    def add_tool(self, tool: 'Tool') -> None:
        """Dynamically register a tool into the bound registry.

        Args:
            tool: The tool to register.

        Raises:
            RuntimeError: If no registry is bound to this context.
            ValueError: If the tool name is already registered.
        """
        if self._registry is None:
            raise RuntimeError(
                'No registry bound to this ToolContext. '
                'Pass a ToolRegistry to ToolContext() or use '
                'AgentRuntime to bind one automatically.'
            )
        self._registry.register(tool)

    def remove_tool(self, name: str) -> None:
        """Dynamically unregister a tool from the bound registry.

        Args:
            name: The name of the tool to remove.

        Raises:
            RuntimeError: If no registry is bound to this context.
            ValueError: If no tool with *name* is registered.
        """
        if self._registry is None:
            raise RuntimeError(
                'No registry bound to this ToolContext. '
                'Pass a ToolRegistry to ToolContext() or use '
                'AgentRuntime to bind one automatically.'
            )
        self._registry.unregister(name)
