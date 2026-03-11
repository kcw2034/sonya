"""Tests for MemoryStore protocol."""

from sonya.pipeline.schemas.types import MemoryStore


class _DummyStore:
    def save(self, session_id, messages):
        pass

    def load(self, session_id, last_n=None):
        return []

    def clear(self, session_id):
        pass


class _IncompleteStore:
    def save(self, session_id, messages):
        pass


def test_dummy_store_satisfies_protocol():
    assert isinstance(_DummyStore(), MemoryStore)


def test_incomplete_store_fails_protocol():
    assert not isinstance(_IncompleteStore(), MemoryStore)
