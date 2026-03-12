"""Tests for AgentRuntime.run_stream()."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.client.base import BaseClient
from sonya.core.exceptions.errors import AgentError
from sonya.core.utils.decorator import tool
from sonya.core.schemas.types import ClientConfig


class DummyStreamClient(BaseClient):
    """Mock client returning pre-configured responses."""

    def __init__(
        self,
        responses: list[Any],
        model: str = 'dummy',
    ) -> None:
        super().__init__(ClientConfig(model=model))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        if self._call_count >= len(self._responses):
            raise RuntimeError('No more mock responses')
        response = self._responses[self._call_count]
        self._call_count += 1
        return response

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(
            messages, **kwargs
        )


def _text_resp(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _tool_resp(
    text: str,
    tool_name: str,
    tool_id: str,
    tool_input: dict[str, Any],
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type='text', text=text),
            SimpleNamespace(
                type='tool_use',
                id=tool_id,
                name=tool_name,
                input=tool_input,
            ),
        ],
        stop_reason='tool_use',
    )


def _handoff_resp(
    text: str, target: str
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type='text', text=text),
            SimpleNamespace(
                type='tool_use',
                id='hid_1',
                name=f'__handoff_to_{target}',
                input={},
            ),
        ],
        stop_reason='tool_use',
    )


@pytest.mark.asyncio
async def test_run_stream_yields_text_then_result() -> None:
    """Text chunk is yielded before the final AgentResult."""
    client = DummyStreamClient([_text_resp('Hello!')])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    runtime = AgentRuntime(agent)

    items: list[Any] = []
    async for item in runtime.run_stream(
        [{'role': 'user', 'content': 'hi'}]
    ):
        items.append(item)

    assert len(items) == 2
    assert items[0] == 'Hello!'
    assert isinstance(items[1], AgentResult)
    assert items[1].text == 'Hello!'


@pytest.mark.asyncio
async def test_run_stream_agent_result_is_last() -> None:
    """AgentResult is always the last yielded item."""
    client = DummyStreamClient([_text_resp('Done')])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    runtime = AgentRuntime(agent)

    items: list[Any] = []
    async for item in runtime.run_stream(
        [{'role': 'user', 'content': 'go'}]
    ):
        items.append(item)

    assert isinstance(items[-1], AgentResult)


@pytest.mark.asyncio
async def test_run_stream_empty_text_not_yielded() -> None:
    """Empty text from LLM is not yielded as a chunk."""
    client = DummyStreamClient([_text_resp('')])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    runtime = AgentRuntime(agent)

    items: list[Any] = []
    async for item in runtime.run_stream(
        [{'role': 'user', 'content': 'hi'}]
    ):
        items.append(item)

    # Only AgentResult, no empty string
    assert len(items) == 1
    assert isinstance(items[0], AgentResult)


@pytest.mark.asyncio
async def test_run_stream_with_tool_call() -> None:
    """Text chunks yielded per-iteration; AgentResult is last."""

    @tool(description='Add two numbers')
    async def add(x: int, y: int) -> str:
        return str(x + y)

    client = DummyStreamClient([
        _tool_resp('Let me add.', 'add', 'tc1', {'x': 1, 'y': 2}),
        _text_resp('Result is 3.'),
    ])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client, tools=[add])
    runtime = AgentRuntime(agent)

    items: list[Any] = []
    async for item in runtime.run_stream(
        [{'role': 'user', 'content': 'add 1+2'}]
    ):
        items.append(item)

    text_items = [i for i in items if isinstance(i, str)]
    result_items = [i for i in items if isinstance(i, AgentResult)]

    assert 'Let me add.' in text_items
    assert 'Result is 3.' in text_items
    assert len(result_items) == 1
    assert result_items[0].text == 'Result is 3.'
    assert isinstance(items[-1], AgentResult)


@pytest.mark.asyncio
async def test_run_stream_handoff() -> None:
    """Handoff yields AgentResult with handoff_to set."""
    client = DummyStreamClient(
        [_handoff_resp('Handing over.', 'other_agent')]
    )
    client.__class__.__name__ = 'AnthropicClient'

    other = Agent(
        name='other_agent',
        client=DummyStreamClient([]),
    )
    agent = Agent(
        name='a', client=client, handoffs=[other]
    )
    runtime = AgentRuntime(agent)

    items: list[Any] = []
    async for item in runtime.run_stream(
        [{'role': 'user', 'content': 'go'}]
    ):
        items.append(item)

    result = items[-1]
    assert isinstance(result, AgentResult)
    assert result.handoff_to == 'other_agent'


@pytest.mark.asyncio
async def test_run_stream_max_iterations_raises() -> None:
    """AgentError raised when max_iterations is exceeded."""

    @tool(description='A tool that loops')
    async def loop_tool(x: int) -> str:
        return 'ok'

    responses = [
        _tool_resp('Thinking.', 'loop_tool', f'tc{i}', {'x': i})
        for i in range(5)
    ]
    client = DummyStreamClient(responses)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[loop_tool],
        max_iterations=3,
    )
    runtime = AgentRuntime(agent)

    with pytest.raises(AgentError):
        async for _ in runtime.run_stream(
            [{'role': 'user', 'content': 'go'}]
        ):
            pass


@pytest.mark.asyncio
async def test_run_stream_history_preserved() -> None:
    """AgentResult history includes all messages."""
    client = DummyStreamClient([_text_resp('Hi!')])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    runtime = AgentRuntime(agent)

    result: AgentResult | None = None
    async for item in runtime.run_stream(
        [{'role': 'user', 'content': 'hello'}]
    ):
        if isinstance(item, AgentResult):
            result = item

    assert result is not None
    roles = [m['role'] for m in result.history]
    assert 'user' in roles
    assert 'assistant' in roles
