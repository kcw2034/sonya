"""Tests for Session dataclass and InMemorySessionStore."""

from __future__ import annotations

import time

import pytest

from sonya.core.models.session import Session, SessionStore
from sonya.core.stores.in_memory import InMemorySessionStore


# --- Session ---

def test_session_defaults() -> None:
    s = Session(session_id='s1', history=[])
    assert s.session_id == 's1'
    assert s.history == []
    assert s.agent_name is None
    assert s.metadata == {}
    assert s.created_at > 0
    assert s.updated_at > 0


def test_session_with_all_fields() -> None:
    now = time.time()
    s = Session(
        session_id='s2',
        history=[{'role': 'user', 'content': 'hello'}],
        agent_name='bot',
        metadata={'key': 'value'},
        created_at=now,
        updated_at=now,
    )
    assert s.session_id == 's2'
    assert len(s.history) == 1
    assert s.agent_name == 'bot'
    assert s.metadata['key'] == 'value'


# --- InMemorySessionStore ---

def test_save_and_load() -> None:
    store = InMemorySessionStore()
    session = Session(
        session_id='abc',
        history=[{'role': 'user', 'content': 'hi'}],
    )
    store.save(session)
    loaded = store.load('abc')
    assert loaded is not None
    assert loaded.session_id == 'abc'
    assert len(loaded.history) == 1


def test_load_missing_returns_none() -> None:
    store = InMemorySessionStore()
    assert store.load('nonexistent') is None


def test_exists_true_after_save() -> None:
    store = InMemorySessionStore()
    store.save(Session(session_id='x', history=[]))
    assert store.exists('x') is True


def test_exists_false_before_save() -> None:
    store = InMemorySessionStore()
    assert store.exists('x') is False


def test_exists_false_after_delete() -> None:
    store = InMemorySessionStore()
    store.save(Session(session_id='y', history=[]))
    store.delete('y')
    assert store.exists('y') is False


def test_delete_nonexistent_is_noop() -> None:
    store = InMemorySessionStore()
    store.delete('ghost')  # should not raise


def test_list_sessions_empty() -> None:
    store = InMemorySessionStore()
    assert store.list_sessions() == []


def test_list_sessions_returns_all_ids() -> None:
    store = InMemorySessionStore()
    store.save(Session(session_id='a', history=[]))
    store.save(Session(session_id='b', history=[]))
    ids = store.list_sessions()
    assert set(ids) == {'a', 'b'}


def test_list_sessions_after_delete() -> None:
    store = InMemorySessionStore()
    store.save(Session(session_id='a', history=[]))
    store.save(Session(session_id='b', history=[]))
    store.delete('a')
    assert store.list_sessions() == ['b']


def test_save_overwrites_existing() -> None:
    store = InMemorySessionStore()
    store.save(Session(session_id='z', history=[]))
    store.save(
        Session(
            session_id='z',
            history=[{'role': 'user', 'content': 'new'}],
        )
    )
    loaded = store.load('z')
    assert loaded is not None
    assert len(loaded.history) == 1


def test_loaded_session_is_isolated_from_original() -> None:
    """Mutating the original should not affect the stored copy."""
    store = InMemorySessionStore()
    history: list[dict] = [{'role': 'user', 'content': 'hi'}]
    session = Session(session_id='iso', history=history)
    store.save(session)
    history.append({'role': 'assistant', 'content': 'hello'})
    loaded = store.load('iso')
    assert loaded is not None
    assert len(loaded.history) == 1


# --- SessionStore protocol conformance ---

def test_in_memory_store_satisfies_protocol() -> None:
    store = InMemorySessionStore()
    assert isinstance(store, SessionStore)
