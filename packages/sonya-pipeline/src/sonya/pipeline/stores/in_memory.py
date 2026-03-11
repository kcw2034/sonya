"""sonya.pipeline.stores.in_memory — In-memory session store."""

from __future__ import annotations

from sonya.core.schemas.memory import NormalizedMessage


class InMemoryStore:
    """Dict-based in-memory session store.

    Messages persist only within the current process.
    Suitable for testing and short-lived sessions.

    Example::

        store = InMemoryStore()
        store.save('session-1', [msg1, msg2])
        loaded = store.load('session-1', last_n=5)
    """

    def __init__(self) -> None:
        self._sessions: dict[
            str, list[NormalizedMessage]
        ] = {}

    def save(
        self,
        session_id: str,
        messages: list[NormalizedMessage],
    ) -> None:
        """Append normalized messages to a session.

        Args:
            session_id: Unique session identifier.
            messages: Messages to append.
        """
        self._sessions.setdefault(
            session_id, []
        ).extend(messages)

    def load(
        self,
        session_id: str,
        last_n: int | None = None,
    ) -> list[NormalizedMessage]:
        """Load normalized messages from a session.

        Args:
            session_id: Unique session identifier.
            last_n: If set, return only the last N messages.

        Returns:
            List of NormalizedMessage (copy).
        """
        msgs = self._sessions.get(session_id, [])
        if last_n is not None:
            return list(msgs[-last_n:])
        return list(msgs)

    def clear(self, session_id: str) -> None:
        """Remove all messages for a session.

        Args:
            session_id: Unique session identifier.
        """
        self._sessions.pop(session_id, None)
