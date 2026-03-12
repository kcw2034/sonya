"""InMemorySessionStore — dict-backed session store."""

from __future__ import annotations

import copy

from sonya.core.models.session import Session


class InMemorySessionStore:
    """In-memory implementation of the SessionStore protocol.

    Suitable for testing and single-process development.
    State is lost when the process exits.

    Stored sessions are deep-copied on save and load to prevent
    external mutations from affecting the stored state.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        """Persist *session*, overwriting any existing entry."""
        self._sessions[session.session_id] = copy.deepcopy(
            session
        )

    def load(self, session_id: str) -> Session | None:
        """Return a copy of the stored session, or None."""
        s = self._sessions.get(session_id)
        if s is None:
            return None
        return copy.deepcopy(s)

    def delete(self, session_id: str) -> None:
        """Remove *session_id* (no-op if absent)."""
        self._sessions.pop(session_id, None)

    def exists(self, session_id: str) -> bool:
        """Return True if *session_id* is present."""
        return session_id in self._sessions

    def list_sessions(self) -> list[str]:
        """Return all session IDs in insertion order."""
        return list(self._sessions.keys())
