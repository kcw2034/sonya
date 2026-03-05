"""Tests for SupervisorRuntime — supervisor delegates to workers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.agent.types import Agent
from sonya.core.client.base import BaseClient
from sonya.core.orchestration.supervisor import (
    SupervisorConfig,
    SupervisorRuntime,
)
from sonya.core.types import ClientConfig


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


def _anthropic_tool_call(
    name: str,
    tool_id: str,
    args: dict[str, Any],
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type='text', text=''),
            SimpleNamespace(
                type='tool_use',
                id=tool_id,
                name=name,
                input=args,
            ),
        ],
        stop_reason='tool_use',
    )


@pytest.mark.asyncio
async def test_supervisor_delegates_to_worker() -> None:
    """Supervisor calls a worker tool, worker responds, supervisor finishes."""
    # Worker: returns a simple text response
    worker_client = DummyClient([_anthropic_text('Worker result')])
    worker_client.__class__.__name__ = 'AnthropicClient'

    worker = Agent(
        name='researcher',
        client=worker_client,
        instructions='I research topics.',
    )

    # Supervisor: first calls ask_researcher, then responds with final text
    supervisor_client = DummyClient([
        _anthropic_tool_call(
            'ask_researcher',
            'tc_w1',
            {'task': 'Research AI trends'},
        ),
        _anthropic_text('Based on research: AI is growing fast.'),
    ])
    supervisor_client.__class__.__name__ = 'AnthropicClient'

    supervisor = Agent(
        name='supervisor',
        client=supervisor_client,
        instructions='I coordinate workers.',
    )

    config = SupervisorConfig(
        supervisor=supervisor,
        workers=[worker],
    )
    runtime = SupervisorRuntime(config)
    result = await runtime.run([
        {'role': 'user', 'content': 'Tell me about AI'}
    ])

    assert result.agent_name == 'supervisor'
    assert 'AI is growing fast' in result.text


@pytest.mark.asyncio
async def test_supervisor_no_workers() -> None:
    """Supervisor without workers just responds directly."""
    client = DummyClient([_anthropic_text('Direct answer')])
    client.__class__.__name__ = 'AnthropicClient'

    supervisor = Agent(
        name='solo',
        client=client,
        instructions='I work alone.',
    )

    config = SupervisorConfig(supervisor=supervisor)
    runtime = SupervisorRuntime(config)
    result = await runtime.run([
        {'role': 'user', 'content': 'Hello'}
    ])

    assert result.text == 'Direct answer'


@pytest.mark.asyncio
async def test_worker_tools_injected() -> None:
    """Worker tools should be added to supervisor's tool list."""
    worker_client = DummyClient([_anthropic_text('ok')])
    worker_client.__class__.__name__ = 'AnthropicClient'

    worker = Agent(name='helper', client=worker_client)

    supervisor_client = DummyClient([_anthropic_text('done')])
    supervisor_client.__class__.__name__ = 'AnthropicClient'

    supervisor = Agent(name='boss', client=supervisor_client)

    config = SupervisorConfig(
        supervisor=supervisor,
        workers=[worker],
    )
    SupervisorRuntime(config)

    tool_names = [t.name for t in supervisor.tools]
    assert 'ask_helper' in tool_names
