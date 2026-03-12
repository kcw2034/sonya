"""Tests for FileSessionStore — JSON file-backed session persistence."""

from __future__ import annotations

import json
from pathlib import Path


from sonya.core.models.session import Session
from sonya.pipeline.stores.file_session_store import FileSessionStore


def _make_session(sid: str, content: str = 'hi') -> Session:
    return Session(
        session_id=sid,
        history=[{'role': 'user', 'content': content}],
        agent_name='test_agent',
    )


# --- save / load ---

def test_save_creates_json_file(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('abc'))
    assert (tmp_path / 'abc.json').exists()


def test_load_returns_saved_session(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('xyz', 'hello'))
    loaded = store.load('xyz')
    assert loaded is not None
    assert loaded.session_id == 'xyz'
    assert loaded.history[0]['content'] == 'hello'


def test_load_missing_returns_none(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    assert store.load('ghost') is None


def test_save_overwrites_existing(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('upd', 'first'))
    store.save(
        Session(
            session_id='upd',
            history=[{'role': 'user', 'content': 'second'}],
        )
    )
    loaded = store.load('upd')
    assert loaded is not None
    assert loaded.history[0]['content'] == 'second'


def test_json_file_is_valid_json(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('valid'))
    raw = (tmp_path / 'valid.json').read_text()
    data = json.loads(raw)
    assert data['session_id'] == 'valid'
    assert 'history' in data
    assert 'created_at' in data
    assert 'updated_at' in data


# --- exists / delete ---

def test_exists_after_save(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('e1'))
    assert store.exists('e1') is True


def test_exists_before_save(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    assert store.exists('missing') is False


def test_delete_removes_file(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('del'))
    store.delete('del')
    assert not (tmp_path / 'del.json').exists()
    assert store.exists('del') is False


def test_delete_nonexistent_is_noop(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.delete('ghost')  # must not raise


# --- list_sessions ---

def test_list_sessions_empty(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    assert store.list_sessions() == []


def test_list_sessions_returns_all_ids(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('s1'))
    store.save(_make_session('s2'))
    ids = store.list_sessions()
    assert set(ids) == {'s1', 's2'}


def test_list_sessions_excludes_deleted(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    store.save(_make_session('keep'))
    store.save(_make_session('gone'))
    store.delete('gone')
    assert store.list_sessions() == ['keep']


# --- directory auto-creation ---

def test_creates_directory_if_missing(tmp_path: Path) -> None:
    nested = tmp_path / 'deep' / 'dir'
    store = FileSessionStore(nested)
    store.save(_make_session('new'))
    assert (nested / 'new.json').exists()


# --- round-trip preserves all fields ---

def test_round_trip_preserves_metadata(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    original = Session(
        session_id='rt',
        history=[{'role': 'user', 'content': 'test'}],
        agent_name='my_agent',
        metadata={'key': 'value', 'count': 3},
    )
    store.save(original)
    loaded = store.load('rt')
    assert loaded is not None
    assert loaded.agent_name == 'my_agent'
    assert loaded.metadata['key'] == 'value'
    assert loaded.metadata['count'] == 3
