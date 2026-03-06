"""sonya.pipeline.client.bridge — ContextBridge (sonya-pack to sonya-core).

Bridge connecting BinContextEngine and sonya-core Agent data flow.
JIT restores message lists from BinContext for Agent execution
and writes Agent results back to BinContext.
"""

from __future__ import annotations

from typing import Any

from sonya.pack import BinContextEngine
from sonya.pipeline.schemas.types import Message


class ContextBridge:
    """Data bridge between sonya-pack (BinContext) and
    sonya-core (Agent).

    Wraps the BinContext engine to provide message lists
    directly usable with sonya-core Agent.run(), and stores
    execution results back.

    Parameters:
        engine: BinContextEngine instance to inject.

    Example::

        from sonya.pack import BinContextEngine
        from sonya.pipeline import ContextBridge

        engine = BinContextEngine('./data')
        bridge = ContextBridge(engine)
        bridge.save_messages('sess-1', [
            {'role': 'user', 'content': 'Hello!'},
        ])
        context = bridge.load_context('sess-1')
        # -> Can be used directly with Agent.run(context)
    """

    def __init__(self, engine: BinContextEngine) -> None:
        self._engine = engine

    @property
    def engine(self) -> BinContextEngine:
        """Return the internal BinContextEngine instance."""
        return self._engine

    # ── Save ─────────────────────────────────────────────────────────────

    def save_messages(
        self,
        session_id: str,
        messages: list[Message],
    ) -> int:
        """Batch save a message list to BinContext.

        Args:
            session_id: Conversation session identifier.
            messages: List in the format
                ``[{"role": "user", "content": "..."}]``.

        Returns:
            Number of messages saved.
        """
        count = 0
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if content:
                self._engine.add_message(
                    session_id, role, content
                )
                count += 1
        return count

    def save_agent_result(
        self,
        session_id: str,
        result: Any,
    ) -> None:
        """Record a sonya-core AgentResult to BinContext.

        Saves AgentResult.text as an assistant message.

        Args:
            session_id: Conversation session identifier.
            result: sonya-core ``AgentResult`` instance.
        """
        text = getattr(result, 'text', None)
        if text:
            self._engine.add_message(
                session_id, 'assistant', text
            )

    # ── Load ─────────────────────────────────────────────────────────────

    def load_context(
        self,
        session_id: str,
        *,
        last_n_turns: int | None = None,
    ) -> list[Message]:
        """JIT restore conversation context from BinContext.

        The returned ``list[dict]`` is directly usable with
        sonya-core ``Agent.run(messages)``.

        Args:
            session_id: Conversation session identifier.
            last_n_turns: If specified, fetch only the last
                N messages.

        Returns:
            List in the format
            ``[{"role": "user", "content": "..."}, ...]``.
        """
        return self._engine.build_context(
            session_id, last_n_turns=last_n_turns
        )

    # ── Utilities ────────────────────────────────────────────────────────

    def list_sessions(self) -> list[str]:
        """Return a list of all registered session IDs."""
        return self._engine.list_sessions()

    def message_count(self, session_id: str) -> int:
        """Return the message count for the given session."""
        session = self._engine.get_session(session_id)
        return len(session.messages)
