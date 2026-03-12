"""Tests for AgentRuntime guardrail enforcement."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.client.provider.base import BaseClient
from sonya.core.exceptions.errors import AgentError, GuardrailError
from sonya.core.schemas.types import ClientConfig, GuardrailConfig
from sonya.core.utils.decorator import tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyClient(BaseClient):
    """Pre-configured mock client."""

    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(
            messages, **kwargs
        )


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _tool_call(
    text: str,
    name: str,
    tid: str,
    args: dict[str, Any],
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type='text', text=text),
            SimpleNamespace(
                type='tool_use',
                id=tid,
                name=name,
                input=args,
            ),
        ],
        stop_reason='tool_use',
    )


@tool(description='Always returns ok')
def noop() -> str:
    return 'ok'


# ---------------------------------------------------------------------------
# GuardrailConfig defaults
# ---------------------------------------------------------------------------

def test_guardrail_config_defaults() -> None:
    """Default GuardrailConfig imposes no limits."""
    gc = GuardrailConfig()
    assert gc.max_tool_calls is None
    assert gc.max_tool_time is None


def test_guardrail_error_is_agent_error() -> None:
    """GuardrailError is a subclass of AgentError."""
    err = GuardrailError('agent', 'reason')
    assert isinstance(err, AgentError)
    assert err.reason == 'reason'


# ---------------------------------------------------------------------------
# max_tool_calls — run()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_tool_calls_within_limit() -> None:
    """Agents that stay within the tool call limit complete normally."""
    client = _DummyClient([
        _tool_call('t1', 'noop', 'c1', {}),
        _text('Done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[noop],
        guardrails=GuardrailConfig(max_tool_calls=2),
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    assert isinstance(result, AgentResult)
    assert result.text == 'Done'


@pytest.mark.asyncio
async def test_max_tool_calls_exceeded_raises() -> None:
    """GuardrailError is raised when tool calls exceed max_tool_calls."""
    # 3 tool-call responses; limit is 2
    resps = [
        _tool_call('t', 'noop', f'c{i}', {})
        for i in range(3)
    ] + [_text('Final')]
    client = _DummyClient(resps)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[noop],
        guardrails=GuardrailConfig(max_tool_calls=2),
    )
    with pytest.raises(GuardrailError) as exc_info:
        await AgentRuntime(agent).run(
            [{'role': 'user', 'content': 'go'}]
        )
    assert 'tool call' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_max_tool_calls_exact_limit_ok() -> None:
    """Exactly hitting max_tool_calls does NOT raise."""
    resps = [
        _tool_call('t', 'noop', 'c1', {}),
        _tool_call('t', 'noop', 'c2', {}),
        _text('Done'),
    ]
    client = _DummyClient(resps)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[noop],
        guardrails=GuardrailConfig(max_tool_calls=2),
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    assert result.text == 'Done'


# ---------------------------------------------------------------------------
# max_tool_calls — run_stream()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stream_max_tool_calls_exceeded() -> None:
    """run_stream() raises GuardrailError on tool call overflow."""
    resps = [
        _tool_call('t', 'noop', f'c{i}', {})
        for i in range(3)
    ] + [_text('Final')]
    client = _DummyClient(resps)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[noop],
        guardrails=GuardrailConfig(max_tool_calls=2),
    )
    with pytest.raises(GuardrailError):
        async for _ in AgentRuntime(agent).run_stream(
            [{'role': 'user', 'content': 'go'}]
        ):
            pass


# ---------------------------------------------------------------------------
# max_tool_time — run()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_tool_time_exceeded_raises() -> None:
    """GuardrailError is raised when cumulative tool time exceeds limit."""

    @tool(description='Slow tool')
    async def slow_tool() -> str:
        await asyncio.sleep(0.05)
        return 'done'

    resps = [
        _tool_call('t', 'slow_tool', 'c1', {}),
        _tool_call('t', 'slow_tool', 'c2', {}),
        _text('Final'),
    ]
    client = _DummyClient(resps)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[slow_tool],
        # 0.03s limit — exceeded after first 0.05s tool call
        guardrails=GuardrailConfig(max_tool_time=0.03),
    )
    with pytest.raises(GuardrailError) as exc_info:
        await AgentRuntime(agent).run(
            [{'role': 'user', 'content': 'go'}]
        )
    assert 'time' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_max_tool_time_within_limit() -> None:
    """Agent completes when tool time stays under the limit."""
    resps = [
        _tool_call('t', 'noop', 'c1', {}),
        _text('Done'),
    ]
    client = _DummyClient(resps)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[noop],
        guardrails=GuardrailConfig(max_tool_time=5.0),
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    assert result.text == 'Done'


# ---------------------------------------------------------------------------
# Guardrails disabled by default
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_guardrails_disabled_by_default() -> None:
    """Agent with default GuardrailConfig runs without restriction."""
    # 5 tool calls — would exceed max_tool_calls=2 if guardrails active
    resps = [
        _tool_call('t', 'noop', f'c{i}', {})
        for i in range(5)
    ] + [_text('Done')]
    client = _DummyClient(resps)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a',
        client=client,
        tools=[noop],
        max_iterations=10,
        # no guardrails kwarg — uses default GuardrailConfig()
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    assert result.text == 'Done'
