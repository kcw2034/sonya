"""sonya.pipeline.schemas.types — Pipeline protocol definitions.

Extensible protocol-based abstractions for pipeline stages
and external data source adapters.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ── Message type ──────────────────────────────────────────────────────────

# Same format as sonya-core Agent.run() message format
Message = dict[str, Any]


# ── Memory store protocol ────────────────────────────────────────────────

from sonya.core.schemas.memory import NormalizedMessage


@runtime_checkable
class MemoryStore(Protocol):
    """Store and retrieve normalized messages by session.

    Args:
        session_id: Unique session identifier.
        messages: List of NormalizedMessage to save.
        last_n: Optional limit to load only the last N messages.
    """

    def save(
        self,
        session_id: str,
        messages: list[NormalizedMessage],
    ) -> None:
        """Save normalized messages to a session."""
        ...

    def load(
        self,
        session_id: str,
        last_n: int | None = None,
    ) -> list[NormalizedMessage]:
        """Load normalized messages from a session."""
        ...

    def clear(self, session_id: str) -> None:
        """Clear all messages in a session."""
        ...


# ── Pipeline stage protocol ──────────────────────────────────────────────

@runtime_checkable
class PipelineStage(Protocol):
    """Pipeline stage that transforms a list of messages.

    Each stage receives a message list and returns
    a transformed message list.
    Used for filtering, summarization, token limiting,
    system prompt injection, etc.

    Example::

        class MyStage:
            def process(self, messages):
                return [
                    m for m in messages
                    if m["role"] != "system"
                ]
    """

    def process(
        self, messages: list[Message]
    ) -> list[Message]:
        """Transform and return a list of messages."""
        ...


# ── Source adapter protocol ──────────────────────────────────────────────

@runtime_checkable
class SourceAdapter(Protocol):
    """Adapter that fetches messages from an external data source.

    Converts conversation data from various external sources
    (files, DB, API, etc.) into the sonya standard message
    format.

    Example::

        class JsonFileAdapter:
            def __init__(self, path: str):
                self._path = path

            def fetch(self) -> list[dict]:
                with open(self._path) as f:
                    return json.load(f)
    """

    def fetch(self) -> list[Message]:
        """Fetch a list of messages from an external source."""
        ...
