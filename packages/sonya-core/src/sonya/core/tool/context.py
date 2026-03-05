"""ToolContext — lightweight run-scoped key-value store."""

from __future__ import annotations

from typing import Any


class ToolContext:
    """Run-scoped key-value store shared across tool executions.

    Provides a simple mutable namespace that tools can use to share
    state within a single agent run.

    Example::

        ctx = ToolContext()
        ctx.set('user_id', 42)
        assert ctx.get('user_id') == 42
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

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
