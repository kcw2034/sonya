"""Tests for BridgeStore."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.schemas.types import MemoryStore
from sonya.pipeline.stores.bridge_store import BridgeStore


class _FakeEngine:
    """Minimal BinContextEngine fake for testing."""

    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}

    def add_message(self, session_id, role, content):
        self._sessions.setdefault(session_id, []).append(
            {'role': role, 'content': content}
        )

    def build_context(self, session_id, *, last_n_turns=None):
        msgs = self._sessions.get(session_id, [])
        if last_n_turns is not None:
            return list(msgs[-last_n_turns:])
        return list(msgs)

    def clear_session(self, session_id):
        self._sessions.pop(session_id, None)


class _FakeBridge:
    """Minimal ContextBridge fake wrapping _FakeEngine."""

    def __init__(self):
        self._engine = _FakeEngine()

    @property
    def engine(self):
        return self._engine

    def save_messages(self, session_id, messages):
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

    def load_context(self, session_id, *, last_n_turns=None):
        return self._engine.build_context(
            session_id, last_n_turns=last_n_turns
        )


def _msg(role: str, content: str) -> NormalizedMessage:
    return NormalizedMessage(role=role, content=content)


def test_satisfies_protocol():
    assert isinstance(BridgeStore(_FakeBridge()), MemoryStore)


def test_save_and_load():
    bridge = _FakeBridge()
    store = BridgeStore(bridge)
    store.save(
        's1',
        [_msg('user', 'hello'), _msg('assistant', 'hi')],
    )
    result = store.load('s1')
    assert len(result) == 2
    assert result[0].role == 'user'
    assert result[0].content == 'hello'
    assert result[1].role == 'assistant'
    assert result[1].content == 'hi'


def test_load_empty():
    store = BridgeStore(_FakeBridge())
    assert store.load('nonexistent') == []


def test_load_last_n():
    bridge = _FakeBridge()
    store = BridgeStore(bridge)
    msgs = [_msg('user', f'm{i}') for i in range(5)]
    store.save('s1', msgs)
    result = store.load('s1', last_n=2)
    assert len(result) == 2
    assert result[0].content == 'm3'


def test_clear():
    bridge = _FakeBridge()
    store = BridgeStore(bridge)
    store.save('s1', [_msg('user', 'hello')])
    store.clear('s1')
    assert store.load('s1') == []
