"""Unit tests for ContextBridge methods: save_agent_result,
list_sessions, message_count, and the engine property."""

from __future__ import annotations

from types import SimpleNamespace

from sonya.pipeline.client.bridge import ContextBridge


# ── Minimal fake engine ──────────────────────────────────────────────────

class _FakeEngine:
    """Minimal BinContextEngine fake for ContextBridge tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, str]]] = {}

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        self._sessions.setdefault(session_id, []).append(
            {'role': role, 'content': content}
        )

    def build_context(
        self,
        session_id: str,
        *,
        last_n_turns: int | None = None,
    ) -> list[dict[str, str]]:
        msgs = self._sessions.get(session_id, [])
        if last_n_turns is not None:
            return list(msgs[-last_n_turns:])
        return list(msgs)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def get_session(self, session_id: str) -> SimpleNamespace:
        msgs = self._sessions.get(session_id, [])
        return SimpleNamespace(messages=msgs)


def _bridge() -> ContextBridge:
    return ContextBridge(_FakeEngine())  # pyright: ignore[reportArgumentType]


def _bridge_with(engine: _FakeEngine) -> ContextBridge:
    return ContextBridge(engine)  # pyright: ignore[reportArgumentType]


# ── engine property ──────────────────────────────────────────────────────

def test_engine_property_returns_underlying_engine() -> None:
    engine = _FakeEngine()
    bridge = _bridge_with(engine)
    assert bridge.engine is engine


# ── save_agent_result ────────────────────────────────────────────────────

def test_save_agent_result_stores_text_as_assistant() -> None:
    bridge = _bridge()
    result = SimpleNamespace(text='Hello from agent')
    bridge.save_agent_result('s1', result)
    ctx = bridge.load_context('s1')
    assert len(ctx) == 1
    assert ctx[0]['role'] == 'assistant'
    assert ctx[0]['content'] == 'Hello from agent'


def test_save_agent_result_empty_text_is_skipped() -> None:
    bridge = _bridge()
    result = SimpleNamespace(text='')
    bridge.save_agent_result('s1', result)
    assert bridge.load_context('s1') == []


def test_save_agent_result_none_text_is_skipped() -> None:
    bridge = _bridge()
    result = SimpleNamespace(text=None)
    bridge.save_agent_result('s1', result)
    assert bridge.load_context('s1') == []


def test_save_agent_result_missing_text_attr_is_skipped() -> None:
    bridge = _bridge()
    result = SimpleNamespace()  # no .text attribute
    bridge.save_agent_result('s1', result)
    assert bridge.load_context('s1') == []


def test_save_agent_result_appends_to_existing_messages() -> None:
    bridge = _bridge()
    bridge.save_messages(
        's2', [{'role': 'user', 'content': 'hi'}]
    )
    result = SimpleNamespace(text='hello')
    bridge.save_agent_result('s2', result)
    ctx = bridge.load_context('s2')
    assert len(ctx) == 2
    assert ctx[-1]['role'] == 'assistant'


# ── list_sessions ────────────────────────────────────────────────────────

def test_list_sessions_empty_when_no_sessions() -> None:
    bridge = _bridge()
    assert bridge.list_sessions() == []


def test_list_sessions_returns_all_session_ids() -> None:
    bridge = _bridge()
    bridge.save_messages(
        'a', [{'role': 'user', 'content': 'hello'}]
    )
    bridge.save_messages(
        'b', [{'role': 'user', 'content': 'world'}]
    )
    ids = bridge.list_sessions()
    assert set(ids) == {'a', 'b'}


def test_list_sessions_reflects_new_saves() -> None:
    bridge = _bridge()
    assert len(bridge.list_sessions()) == 0
    bridge.save_messages(
        'new', [{'role': 'user', 'content': 'x'}]
    )
    assert len(bridge.list_sessions()) == 1


# ── message_count ────────────────────────────────────────────────────────

def test_message_count_zero_for_empty_session() -> None:
    bridge = _bridge()
    assert bridge.message_count('empty') == 0


def test_message_count_reflects_saved_messages() -> None:
    bridge = _bridge()
    msgs = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]
    bridge.save_messages('s', msgs)
    assert bridge.message_count('s') == 2


def test_message_count_grows_after_save_agent_result() -> None:
    bridge = _bridge()
    bridge.save_messages(
        's', [{'role': 'user', 'content': 'hi'}]
    )
    before = bridge.message_count('s')
    bridge.save_agent_result('s', SimpleNamespace(text='ok'))
    assert bridge.message_count('s') == before + 1


def test_message_count_skips_empty_content_messages() -> None:
    """save_messages skips empty content; count must reflect that."""
    bridge = _bridge()
    bridge.save_messages('s', [
        {'role': 'user', 'content': 'hello'},
        {'role': 'user', 'content': ''},   # skipped
    ])
    assert bridge.message_count('s') == 1
