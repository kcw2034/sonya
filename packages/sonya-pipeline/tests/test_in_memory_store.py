"""Tests for InMemoryStore."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.schemas.types import MemoryStore
from sonya.pipeline.stores.in_memory import InMemoryStore


def _msg(role: str, content: str) -> NormalizedMessage:
    return NormalizedMessage(role=role, content=content)


def test_satisfies_protocol():
    assert isinstance(InMemoryStore(), MemoryStore)


def test_save_and_load():
    store = InMemoryStore()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    store.save('s1', msgs)
    assert store.load('s1') == msgs


def test_load_empty_session():
    store = InMemoryStore()
    assert store.load('nonexistent') == []


def test_load_last_n():
    store = InMemoryStore()
    msgs = [_msg('user', f'm{i}') for i in range(5)]
    store.save('s1', msgs)
    result = store.load('s1', last_n=2)
    assert len(result) == 2
    assert result[0].content == 'm3'
    assert result[1].content == 'm4'


def test_save_appends():
    store = InMemoryStore()
    store.save('s1', [_msg('user', 'a')])
    store.save('s1', [_msg('user', 'b')])
    assert len(store.load('s1')) == 2


def test_clear():
    store = InMemoryStore()
    store.save('s1', [_msg('user', 'hello')])
    store.clear('s1')
    assert store.load('s1') == []


def test_clear_nonexistent():
    store = InMemoryStore()
    store.clear('nonexistent')  # should not raise
