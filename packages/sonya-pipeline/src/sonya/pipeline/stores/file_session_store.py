"""FileSessionStore — JSON file-backed session persistence."""

from __future__ import annotations

import json
from pathlib import Path

from sonya.core.models.session import Session


class FileSessionStore:
    """JSON file-backed implementation of the SessionStore protocol.

    Each session is stored as ``{directory}/{session_id}.json``.
    The directory is created automatically if it does not exist.

    Args:
        directory: Path to the directory where session files are stored.
    """

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._dir / f'{session_id}.json'

    def save(self, session: Session) -> None:
        """Persist *session* as a JSON file, overwriting if present."""
        data = {
            'session_id': session.session_id,
            'history': session.history,
            'agent_name': session.agent_name,
            'metadata': session.metadata,
            'created_at': session.created_at,
            'updated_at': session.updated_at,
        }
        self._path(session.session_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def load(self, session_id: str) -> Session | None:
        """Return the deserialized session, or None if absent."""
        p = self._path(session_id)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding='utf-8'))
        return Session(
            session_id=data['session_id'],
            history=data['history'],
            agent_name=data.get('agent_name'),
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at', 0.0),
            updated_at=data.get('updated_at', 0.0),
        )

    def delete(self, session_id: str) -> None:
        """Remove the session file (no-op if absent)."""
        p = self._path(session_id)
        if p.exists():
            p.unlink()

    def exists(self, session_id: str) -> bool:
        """Return True if the session file exists."""
        return self._path(session_id).exists()

    def list_sessions(self) -> list[str]:
        """Return session IDs sorted by file modification time."""
        files = sorted(
            self._dir.glob('*.json'),
            key=lambda f: f.stat().st_mtime,
        )
        return [f.stem for f in files]
