"""Tests for handoff chain between agents."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime, _HANDOFF_PREFIX
from sonya.core.models.agent import Agent
from sonya.core.client.base import BaseClient
from sonya.core.models.runner import Runner, RunnerConfig
from sonya.core.schemas.types import ClientConfig


class DummyClient(BaseClient):
    """Mock client returning pre-configured responses."""

    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _anthropic_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _anthropic_handoff(target_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type='text', text=''),
            SimpleNamespace(
                type='tool_use',
                id='tc_handoff',
                name=f'{_HANDOFF_PREFIX}{target_name}',
                input={},
            ),
        ],
        stop_reason='tool_use',
    )


@pytest.mark.asyncio
async def test_single_handoff() -> None:
    """Agent A hands off to Agent B, and B responds."""
    client_a = DummyClient([_anthropic_handoff('agent_b')])
    client_a.__class__.__name__ = 'AnthropicClient'

    client_b = DummyClient([_anthropic_text('Hello from B')])
    client_b.__class__.__name__ = 'AnthropicClient'

    agent_b = Agent(
        name='agent_b',
        client=client_b,
        instructions='I am agent B',
    )
    agent_a = Agent(
        name='agent_a',
        client=client_a,
        instructions='I am agent A',
        handoffs=[agent_b],
    )

    config = RunnerConfig(agents=[agent_a, agent_b])
    runner = Runner(config)
    result = await runner.run(
        [{'role': 'user', 'content': 'Start'}],
        start_agent='agent_a',
    )

    assert result.agent_name == 'agent_b'
    assert result.text == 'Hello from B'


@pytest.mark.asyncio
async def test_chain_handoff_a_b_c() -> None:
    """A -> B -> C chain."""
    client_a = DummyClient([_anthropic_handoff('agent_b')])
    client_a.__class__.__name__ = 'AnthropicClient'

    client_b = DummyClient([_anthropic_handoff('agent_c')])
    client_b.__class__.__name__ = 'AnthropicClient'

    client_c = DummyClient([_anthropic_text('Final from C')])
    client_c.__class__.__name__ = 'AnthropicClient'

    agent_c = Agent(name='agent_c', client=client_c)
    agent_b = Agent(
        name='agent_b', client=client_b, handoffs=[agent_c]
    )
    agent_a = Agent(
        name='agent_a', client=client_a, handoffs=[agent_b]
    )

    config = RunnerConfig(
        agents=[agent_a, agent_b, agent_c]
    )
    runner = Runner(config)
    result = await runner.run(
        [{'role': 'user', 'content': 'Go'}],
        start_agent='agent_a',
    )

    assert result.agent_name == 'agent_c'
    assert result.text == 'Final from C'


@pytest.mark.asyncio
async def test_runner_callback() -> None:
    """Callbacks should be invoked during handoff chain."""
    events: list[str] = []

    class Tracker:
        async def on_agent_start(
            self, name: str, msgs: list[Any]
        ) -> None:
            events.append(f'start:{name}')

        async def on_agent_end(self, result: Any) -> None:
            events.append(f'end:{result.agent_name}')

        async def on_handoff(
            self, from_a: str, to_a: str
        ) -> None:
            events.append(f'handoff:{from_a}->{to_a}')

    client_a = DummyClient([_anthropic_handoff('b')])
    client_a.__class__.__name__ = 'AnthropicClient'

    client_b = DummyClient([_anthropic_text('Done')])
    client_b.__class__.__name__ = 'AnthropicClient'

    b = Agent(name='b', client=client_b)
    a = Agent(name='a', client=client_a, handoffs=[b])

    config = RunnerConfig(
        agents=[a, b], callbacks=[Tracker()]
    )
    runner = Runner(config)
    await runner.run([{'role': 'user', 'content': 'Hi'}])

    assert 'start:a' in events
    assert 'end:a' in events
    assert 'handoff:a->b' in events
    assert 'start:b' in events
    assert 'end:b' in events


from sonya.core.utils.router import ContextRouter


@pytest.mark.asyncio
async def test_handoff_with_router() -> None:
    """Router-enabled handoff preserves full history for same provider."""
    client_a = DummyClient([_anthropic_handoff('agent_b')])
    client_a.__class__.__name__ = 'AnthropicClient'

    client_b = DummyClient([_anthropic_text('Done')])
    client_b.__class__.__name__ = 'AnthropicClient'

    agent_b = Agent(name='agent_b', client=client_b)
    agent_a = Agent(
        name='agent_a',
        client=client_a,
        handoffs=[agent_b],
    )

    router = ContextRouter()
    config = RunnerConfig(
        agents=[agent_a, agent_b],
        router=router,
    )
    runner = Runner(config)
    result = await runner.run(
        [{'role': 'user', 'content': 'Go'}],
        start_agent='agent_a',
    )

    assert result.agent_name == 'agent_b'
    assert result.text == 'Done'


@pytest.mark.asyncio
async def test_handoff_without_router_unchanged() -> None:
    """Without router, existing fallback behavior is preserved."""
    client_a = DummyClient([_anthropic_handoff('agent_b')])
    client_a.__class__.__name__ = 'AnthropicClient'

    client_b = DummyClient([_anthropic_text('Done')])
    client_b.__class__.__name__ = 'AnthropicClient'

    agent_b = Agent(name='agent_b', client=client_b)
    agent_a = Agent(
        name='agent_a',
        client=client_a,
        handoffs=[agent_b],
    )

    config = RunnerConfig(agents=[agent_a, agent_b])
    runner = Runner(config)
    result = await runner.run(
        [{'role': 'user', 'content': 'Go'}],
        start_agent='agent_a',
    )

    assert result.agent_name == 'agent_b'
    assert result.text == 'Done'
