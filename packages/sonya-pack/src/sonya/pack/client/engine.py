"""sonya.pack.client.engine — BinContext core engine

Append-Only Binary Log + Metadata Index + JIT Context Builder
architecture core implementation. Pure UTF-8 bytes are stored in
`.bin` files, while a separate metadata index tracks each message's
offset and length.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict

from sonya.pack.schemas.schema import MessageMeta, SessionIndex


# -- Type hints ----------------------------------------------------

class MessageDict(TypedDict):
    """Dictionary returned by build_context for each message."""

    role: str
    content: str


# -- BinContext Engine ---------------------------------------------

class BinContextEngine:
    """Lightweight binary context engine.

    Parameters:
        data_dir: Directory path for storing `.bin` files and
            metadata JSON.

    Example::

        engine = BinContextEngine('./data')
        engine.add_message('sess-1', 'user', 'Hello!')
        context = engine.build_context('sess-1', last_n_turns=5)
    """

    # Constants
    _BIN_FILENAME = 'context.bin'
    _META_FILENAME = 'metadata.json'

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._bin_path = self._data_dir / self._BIN_FILENAME
        self._meta_path = self._data_dir / self._META_FILENAME

        # Session index — managed in memory, persisted to JSON
        self._sessions: dict[str, SessionIndex] = {}

        # Load existing metadata if present
        if self._meta_path.exists():
            self._load_metadata()

    # -- Public API ------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        text: str,
        *,
        token_count: int | None = None,
    ) -> MessageMeta:
        """Append text to the binary log and update metadata.

        Args:
            session_id: Conversation session identifier.
            role: Speaker ("user" | "assistant" | "system").
            text: Raw message text to store.
            token_count: (Optional) Estimated token count.

        Returns:
            Created `MessageMeta` instance.
        """
        # 1) UTF-8 encoding
        data = text.encode('utf-8')

        # 2) Append-Only write — current EOF is the offset
        with open(self._bin_path, 'ab') as f:
            offset = f.tell()
            f.write(data)

        # 3) Create metadata
        meta = MessageMeta(
            role=role,
            offset=offset,
            length=len(data),
            token_count=token_count,
        )

        # 4) Update session index
        session = self._ensure_session(session_id)
        session.messages.append(meta)

        # 5) Persist metadata
        self._save_metadata()

        return meta

    def build_context(
        self,
        session_id: str,
        *,
        last_n_turns: int | None = None,
    ) -> list[MessageDict]:
        """Restore conversation context from binary log via JIT.

        Reads specific byte ranges from the `.bin` file based on
        metadata, decoding them to text to build a prompt list.

        Args:
            session_id: Conversation session identifier.
            last_n_turns: Fetch only the last N messages.
                `None` returns the entire conversation.

        Returns:
            List of `{"role": "user", "content": "..."}` dicts.

        Raises:
            KeyError: Non-existent session ID.
            FileNotFoundError: `.bin` file missing.
        """
        session = self._get_session(session_id)
        targets = session.messages

        # Filter to last N turns
        if last_n_turns is not None and last_n_turns > 0:
            targets = targets[-last_n_turns:]

        # JIT read — seek/read based O(1) access
        result: list[MessageDict] = []
        with open(self._bin_path, 'rb') as f:
            for meta in targets:
                f.seek(meta.offset)
                raw = f.read(meta.length)
                content = raw.decode('utf-8')
                result.append(
                    MessageDict(role=meta.role, content=content)
                )

        return result

    def get_session(self, session_id: str) -> SessionIndex:
        """Retrieve session metadata.

        Args:
            session_id: Conversation session identifier.

        Returns:
            The session's `SessionIndex`.

        Raises:
            KeyError: Non-existent session ID.
        """
        return self._get_session(session_id)

    def list_sessions(self) -> list[str]:
        """Return a list of all registered session IDs."""
        return list(self._sessions.keys())

    # -- Metadata persistence --------------------------------------

    def _save_metadata(self) -> None:
        """Save the entire session index to a JSON file."""
        payload = {
            sid: session.model_dump(mode='json')
            for sid, session in self._sessions.items()
        }
        with open(self._meta_path, 'w', encoding='utf-8') as f:
            json.dump(
                payload, f, ensure_ascii=False, indent=2
            )

    def _load_metadata(self) -> None:
        """Restore the session index from a JSON file."""
        with open(self._meta_path, encoding='utf-8') as f:
            payload: dict = json.load(f)
        for sid, data in payload.items():
            self._sessions[sid] = SessionIndex.model_validate(
                data
            )

    # -- Internal helpers ------------------------------------------

    def _ensure_session(
        self, session_id: str
    ) -> SessionIndex:
        """Create a session if missing, else return existing."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionIndex(
                session_id=session_id
            )
        return self._sessions[session_id]

    def _get_session(
        self, session_id: str
    ) -> SessionIndex:
        """Retrieve a session or raise KeyError if missing."""
        try:
            return self._sessions[session_id]
        except KeyError:
            raise KeyError(
                f"Session '{session_id}' not found. "
                f"Registered sessions: {self.list_sessions()}"
            ) from None
