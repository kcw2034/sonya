"""Integration tests for Runner session persistence."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent import Agent
from sonya.core.models.runner import Runner, RunnerConfig
from sonya.core.models.session import Session
from sonya.core.stores.in_memory import InMemorySessionStore
from sonya.core.client.base import BaseClient
from sonya.core.schemas.types import ClientConfig


class _DummyClient(BaseClient):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        if self._call_count >= len(self._responses):
            raise RuntimeError('No more responses')
        r = self._responses[self._call_count]
        self._call_count += 1
        return r

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _make_client(*texts: str) -> _DummyClient:
    client = _DummyClient([_text_response(t) for t in texts])
    client.__class__.__name__ = 'AnthropicClient'
    return client


# --- Session auto-save ---

@pytest.mark.asyncio
async def test_runner_saves_session_after_run() -> None:
    """Runner with session_store must persist session after each run."""
    store = InMemorySessionStore()
    agent = Agent(
        name='agent',
        instructions='help',
        client=_make_client('Hello!'),
    )
    runner = Runner(RunnerConfig(
        agents=[agent],
        session_store=store,
    ))
    result = await runner.run(
        [{'role': 'user', 'content': 'hi'}],
        session_id='sess1',
    )
    assert result.text == 'Hello!'
    assert store.exists('sess1')
    saved = store.load('sess1')
    assert saved is not None
    assert len(saved.history) >= 1


@pytest.mark.asyncio
async def test_runner_auto_generates_session_id_when_store_set() -> None:
    """If store is set but no session_id provided, an ID is auto-generated."""
    store = InMemorySessionStore()
    agent = Agent(
        name='agent',
        instructions='help',
        client=_make_client('Hi'),
    )
    runner = Runner(RunnerConfig(
        agents=[agent],
        session_store=store,
    ))
    result = await runner.run(
        [{'role': 'user', 'content': 'hello'}],
    )
    assert result.text == 'Hi'
    sessions = store.list_sessions()
    assert len(sessions) == 1
    # session_id is recorded in metadata
    assert 'session_id' in result.metadata


@pytest.mark.asyncio
async def test_runner_resumes_session_with_previous_history() -> None:
    """Providing session_id of an existing session prepends its history."""
    store = InMemorySessionStore()
    prior_history = [
        {'role': 'user', 'content': 'first turn'},
        {'role': 'assistant', 'content': 'first reply'},
    ]
    store.save(Session(
        session_id='resume',
        history=prior_history,
        agent_name='agent',
    ))

    # The dummy client will see all messages including resumed history
    received_messages: list[list[dict]] = []

    class _CapturingClient(BaseClient):
        def __init__(self) -> None:
            super().__init__(ClientConfig(model='dummy'))

        async def _provider_generate(
            self,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> Any:
            received_messages.append(list(messages))
            return _text_response('second reply')

        async def _provider_generate_stream(
            self,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> AsyncIterator[Any]:
            yield await self._provider_generate(
                messages, **kwargs
            )

    cap = _CapturingClient()
    cap.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='agent',
        instructions='help',
        client=cap,
    )
    runner = Runner(RunnerConfig(
        agents=[agent],
        session_store=store,
    ))
    await runner.run(
        [{'role': 'user', 'content': 'second turn'}],
        session_id='resume',
    )
    # The messages sent to LLM should include prior history
    assert len(received_messages) == 1
    msg_roles = [m['role'] for m in received_messages[0]]
    assert 'user' in msg_roles
    # Prior content should appear somewhere in the combined history
    all_content = ' '.join(
        m.get('content', '') for m in received_messages[0]
        if isinstance(m.get('content'), str)
    )
    assert 'first turn' in all_content or 'first reply' in all_content


@pytest.mark.asyncio
async def test_runner_updates_session_after_run() -> None:
    """Running again with same session_id must update the stored history."""
    store = InMemorySessionStore()
    agent = Agent(
        name='agent',
        instructions='help',
        client=_make_client('reply1', 'reply2'),
    )
    runner = Runner(RunnerConfig(
        agents=[agent],
        session_store=store,
    ))
    await runner.run(
        [{'role': 'user', 'content': 'turn1'}],
        session_id='upd',
    )
    first_save = store.load('upd')
    assert first_save is not None
    first_len = len(first_save.history)

    # New agent instance with new client for second call
    agent2 = Agent(
        name='agent',
        instructions='help',
        client=_make_client('reply2'),
    )
    runner2 = Runner(RunnerConfig(
        agents=[agent2],
        session_store=store,
    ))
    await runner2.run(
        [{'role': 'user', 'content': 'turn2'}],
        session_id='upd',
    )
    second_save = store.load('upd')
    assert second_save is not None
    # History must have grown
    assert len(second_save.history) > first_len


@pytest.mark.asyncio
async def test_runner_without_store_behaves_as_before() -> None:
    """Runner without session_store must work exactly as before."""
    agent = Agent(
        name='agent',
        instructions='help',
        client=_make_client('Normal reply'),
    )
    runner = Runner(RunnerConfig(agents=[agent]))
    result = await runner.run(
        [{'role': 'user', 'content': 'hello'}],
    )
    assert result.text == 'Normal reply'
    assert 'session_id' not in result.metadata


@pytest.mark.asyncio
async def test_session_metadata_contains_session_id() -> None:
    store = InMemorySessionStore()
    agent = Agent(
        name='agent',
        instructions='help',
        client=_make_client('ok'),
    )
    runner = Runner(RunnerConfig(
        agents=[agent],
        session_store=store,
    ))
    result = await runner.run(
        [{'role': 'user', 'content': 'go'}],
        session_id='my-session',
    )
    assert result.metadata.get('session_id') == 'my-session'
