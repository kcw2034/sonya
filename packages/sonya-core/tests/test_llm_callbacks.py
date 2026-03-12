"""Tests for on_llm_start / on_llm_end AgentCallback hooks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent import Agent
from sonya.core.models.agent_runtime import AgentRuntime
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
        r = self._responses[self._call_count]
        self._call_count += 1
        return r

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _text(t: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=t)],
        stop_reason='end_turn',
    )


def _client(*texts: str) -> _DummyClient:
    c = _DummyClient([_text(t) for t in texts])
    c.__class__.__name__ = 'AnthropicClient'
    return c


# --- Recording callback ---

class _RecordingCallback:
    def __init__(self) -> None:
        self.llm_start_calls: list[dict] = []
        self.llm_end_calls: list[dict] = []

    async def on_llm_start(
        self,
        agent_name: str,
        iteration: int,
        message_count: int,
    ) -> None:
        self.llm_start_calls.append({
            'agent_name': agent_name,
            'iteration': iteration,
            'message_count': message_count,
        })

    async def on_llm_end(
        self,
        agent_name: str,
        iteration: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> None:
        self.llm_end_calls.append({
            'agent_name': agent_name,
            'iteration': iteration,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'latency_ms': latency_ms,
        })


# --- Tests ---

@pytest.mark.asyncio
async def test_on_llm_start_called_before_generate() -> None:
    cb = _RecordingCallback()
    agent = Agent(
        name='a',
        instructions='help',
        client=_client('hello'),
        callbacks=[cb],
    )
    await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert len(cb.llm_start_calls) == 1
    assert cb.llm_start_calls[0]['agent_name'] == 'a'
    assert cb.llm_start_calls[0]['iteration'] == 0


@pytest.mark.asyncio
async def test_on_llm_end_called_after_generate() -> None:
    cb = _RecordingCallback()
    agent = Agent(
        name='b',
        instructions='help',
        client=_client('done'),
        callbacks=[cb],
    )
    await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert len(cb.llm_end_calls) == 1
    call = cb.llm_end_calls[0]
    assert call['agent_name'] == 'b'
    assert call['iteration'] == 0
    assert call['latency_ms'] >= 0


@pytest.mark.asyncio
async def test_on_llm_start_end_called_per_iteration() -> None:
    """Two-iteration run (with tool call) fires callbacks twice."""
    from sonya.core.utils.decorator import tool

    @tool()
    async def echo(msg: str) -> str:
        """Echo tool."""
        return msg

    tool_response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type='tool_use',
                id='tc1',
                name='echo',
                input={'msg': 'hi'},
            )
        ],
        stop_reason='tool_use',
    )
    text_response = _text('done')

    c = _DummyClient([tool_response, text_response])
    c.__class__.__name__ = 'AnthropicClient'

    cb = _RecordingCallback()
    agent = Agent(
        name='c',
        instructions='help',
        client=c,
        tools=[echo],
        callbacks=[cb],
    )
    await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    assert len(cb.llm_start_calls) == 2
    assert len(cb.llm_end_calls) == 2
    assert cb.llm_start_calls[0]['iteration'] == 0
    assert cb.llm_start_calls[1]['iteration'] == 1


@pytest.mark.asyncio
async def test_on_llm_start_receives_message_count() -> None:
    cb = _RecordingCallback()
    messages = [
        {'role': 'user', 'content': 'msg1'},
        {'role': 'assistant', 'content': 'msg2'},
        {'role': 'user', 'content': 'msg3'},
    ]
    agent = Agent(
        name='d',
        instructions='help',
        client=_client('ok'),
        callbacks=[cb],
    )
    await AgentRuntime(agent).run(messages)
    # message_count should reflect number of formatted messages
    assert cb.llm_start_calls[0]['message_count'] >= 1


@pytest.mark.asyncio
async def test_callback_without_llm_hooks_does_not_raise() -> None:
    """Callbacks lacking on_llm_start/end must not break execution."""
    class _LegacyCallback:
        async def on_iteration_start(
            self, agent_name: str, iteration: int
        ) -> None:
            pass

    agent = Agent(
        name='e',
        instructions='help',
        client=_client('fine'),
        callbacks=[_LegacyCallback()],
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'fine'


@pytest.mark.asyncio
async def test_on_llm_end_latency_is_positive_float() -> None:
    cb = _RecordingCallback()
    agent = Agent(
        name='f',
        instructions='help',
        client=_client('ok'),
        callbacks=[cb],
    )
    await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    latency = cb.llm_end_calls[0]['latency_ms']
    assert isinstance(latency, float)
    assert latency >= 0.0
