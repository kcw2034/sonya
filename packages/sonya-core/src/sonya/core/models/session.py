"""Session — conversation state and SessionStore protocol."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class Session:
    """Persistent conversation state for a single agent session.

    Args:
        session_id: Unique identifier for this session.
        history: Provider-native message history
            (list of role/content dicts).
        agent_name: Name of the agent that owns this session.
        metadata: Arbitrary key-value metadata (usage stats,
            tags, etc.).
        created_at: Unix timestamp when the session was first
            created.
        updated_at: Unix timestamp of the last save.
    """

    session_id: str
    history: list[dict[str, Any]]
    agent_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@runtime_checkable
class SessionStore(Protocol):
    """Protocol for persisting and retrieving :class:`Session` objects.

    Implementations may use any storage backend (in-memory,
    JSON files, SQL, Redis, etc.).  sonya-core ships with
    :class:`~sonya.core.stores.in_memory.InMemorySessionStore`;
    durable alternatives live in ``sonya-pipeline``.
    """

    def save(self, session: Session) -> None:
        """Persist *session*, overwriting any existing entry."""
        ...

    def load(self, session_id: str) -> Session | None:
        """Return the session for *session_id*, or None if absent."""
        ...

    def delete(self, session_id: str) -> None:
        """Remove the session for *session_id* (no-op if absent)."""
        ...

    def exists(self, session_id: str) -> bool:
        """Return True if *session_id* is present in the store."""
        ...

    def list_sessions(self) -> list[str]:
        """Return all stored session IDs in insertion order."""
        ...
