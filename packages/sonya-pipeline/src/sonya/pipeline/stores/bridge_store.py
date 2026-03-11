"""sonya.pipeline.stores.bridge_store — Persistent store via ContextBridge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sonya.core.schemas.memory import NormalizedMessage

if TYPE_CHECKING:
    from sonya.pipeline.client.bridge import ContextBridge


class BridgeStore:
    """Persistent session store backed by ContextBridge.

    Delegates storage to BinContext via ContextBridge,
    providing durable session memory that survives
    process restarts.

    Note:
        First iteration stores role + content only.
        tool_calls/tool_results are not persisted.

    Args:
        bridge: ContextBridge instance to delegate to.

    Example::

        from sonya.pack import BinContextEngine
        from sonya.pipeline import ContextBridge, BridgeStore

        engine = BinContextEngine('./data')
        bridge = ContextBridge(engine)
        store = BridgeStore(bridge)
        store.save('session-1', normalized_msgs)
    """

    def __init__(self, bridge: ContextBridge) -> None:
        self._bridge = bridge

    def save(
        self,
        session_id: str,
        messages: list[NormalizedMessage],
    ) -> None:
        """Save normalized messages via ContextBridge.

        Converts NormalizedMessage to dict format
        and delegates to bridge.save_messages().

        Args:
            session_id: Unique session identifier.
            messages: Messages to save.
        """
        raw = [
            {'role': m.role, 'content': m.content}
            for m in messages
        ]
        self._bridge.save_messages(session_id, raw)

    def load(
        self,
        session_id: str,
        last_n: int | None = None,
    ) -> list[NormalizedMessage]:
        """Load messages from ContextBridge as NormalizedMessage.

        Args:
            session_id: Unique session identifier.
            last_n: If set, return only the last N messages.

        Returns:
            List of NormalizedMessage.
        """
        raw = self._bridge.load_context(
            session_id, last_n_turns=last_n,
        )
        return [
            NormalizedMessage(
                role=m.get('role', 'user'),
                content=m.get('content', ''),
            )
            for m in raw
        ]

    def clear(self, session_id: str) -> None:
        """Clear all messages for a session.

        Args:
            session_id: Unique session identifier.
        """
        self._bridge.engine.clear_session(session_id)
