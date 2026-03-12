"""Tests for parallel/sequential/bounded tool execution strategies."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent import Agent, AgentResult
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.client.base import BaseClient
from sonya.core.models.tool_registry import ToolRegistry
from sonya.core.schemas.types import ClientConfig, GuardrailConfig
from sonya.core.utils.decorator import tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyClient(BaseClient):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        if self._call_count >= len(self._responses):
            raise RuntimeError('No more mock responses')
        r = self._responses[self._call_count]
        self._call_count += 1
        return r

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _multi_tool(tools_: list[tuple[str, str, dict[str, Any]]]) -> SimpleNamespace:
    """Build a mock Anthropic response with multiple tool calls."""
    blocks: list[Any] = []
    for name, tool_id, inputs in tools_:
        blocks.append(SimpleNamespace(
            type='tool_use',
            id=tool_id,
            name=name,
            input=inputs,
        ))
    return SimpleNamespace(
        content=blocks,
        stop_reason='tool_use',
    )


# ---------------------------------------------------------------------------
# ToolRegistry unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_many_parallel_default() -> None:
    """execute_many runs tools concurrently by default."""
    started: list[float] = []
    finished: list[float] = []

    async def slow_tool(x: int) -> str:
        started.append(time.monotonic())
        await asyncio.sleep(0.05)
        finished.append(time.monotonic())
        return str(x)

    t1 = tool(name='t1', description='')(lambda: None)
    t1.fn = lambda: slow_tool(1)  # type: ignore[method-assign]

    registry = ToolRegistry()

    async def make_fn(val: int):  # type: ignore[return]
        async def fn() -> str:
            started.append(time.monotonic())
            await asyncio.sleep(0.05)
            finished.append(time.monotonic())
            return str(val)
        return fn

    # Register 3 tools each sleeping 50ms
    from sonya.core.models.tool import Tool

    fns = [await make_fn(i) for i in range(3)]
    for i, fn in enumerate(fns):
        registry.register(Tool(
            name=f'slow_{i}',
            description='slow',
            fn=fn,
        ))

    calls = [(f'slow_{i}', f'id_{i}', {}) for i in range(3)]
    t_start = time.monotonic()
    results = await registry.execute_many(calls)
    elapsed = time.monotonic() - t_start

    # If parallel: ~50ms. If sequential: ~150ms.
    assert elapsed < 0.12, f'Expected parallel (<120ms), got {elapsed*1000:.0f}ms'
    assert len(results) == 3
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_execute_sequential() -> None:
    """execute_sequential runs tools one at a time."""
    order: list[int] = []

    from sonya.core.models.tool import Tool

    registry = ToolRegistry()
    for i in range(3):
        val = i

        async def fn(v: int = val) -> str:
            order.append(v)
            return str(v)

        registry.register(Tool(name=f't{i}', description='', fn=fn))

    calls = [(f't{i}', f'id_{i}', {}) for i in range(3)]
    results = await registry.execute_sequential(calls)

    assert order == [0, 1, 2]
    assert len(results) == 3
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_execute_many_bounded_concurrency() -> None:
    """execute_many with max_concurrency limits simultaneous executions."""
    active = 0
    peak = 0

    from sonya.core.models.tool import Tool

    registry = ToolRegistry()
    for i in range(5):
        async def fn(a: int = i) -> str:  # noqa: B023
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return str(a)

        registry.register(Tool(name=f't{i}', description='', fn=fn))

    calls = [(f't{i}', f'id_{i}', {}) for i in range(5)]
    results = await registry.execute_many(calls, max_concurrency=2)

    assert peak <= 2, f'Peak concurrency {peak} exceeded limit of 2'
    assert len(results) == 5
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_execute_many_no_limit() -> None:
    """execute_many without max_concurrency allows full parallelism."""
    active = 0
    peak = 0

    from sonya.core.models.tool import Tool

    registry = ToolRegistry()
    for i in range(5):
        async def fn(a: int = i) -> str:  # noqa: B023
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return str(a)

        registry.register(Tool(name=f't{i}', description='', fn=fn))

    calls = [(f't{i}', f'id_{i}', {}) for i in range(5)]
    await registry.execute_many(calls)

    assert peak >= 2  # at least some parallel execution occurred


@pytest.mark.asyncio
async def test_execute_sequential_failure_continues() -> None:
    """execute_sequential continues after a tool failure."""
    from sonya.core.models.tool import Tool

    registry = ToolRegistry()

    async def fail_fn() -> str:
        raise ValueError('oops')

    async def ok_fn() -> str:
        return 'ok'

    registry.register(Tool(name='fail', description='', fn=fail_fn))
    registry.register(Tool(name='ok', description='', fn=ok_fn))

    calls = [('fail', 'id_0', {}), ('ok', 'id_1', {})]
    results = await registry.execute_sequential(calls)

    assert results[0].success is False
    assert results[1].success is True


# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_parallel_tool_execution_default() -> None:
    """Agent.parallel_tool_execution defaults to True."""

    client = DummyClient([_text('done')])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)

    assert agent.parallel_tool_execution is True


@pytest.mark.asyncio
async def test_agent_sequential_mode_runs_tools_in_order() -> None:
    """parallel_tool_execution=False runs tools sequentially."""
    order: list[str] = []

    @tool(description='first')
    async def first_tool() -> str:
        order.append('first')
        await asyncio.sleep(0.01)
        return 'first'

    @tool(description='second')
    async def second_tool() -> str:
        order.append('second')
        return 'second'

    client = DummyClient([
        _multi_tool([
            ('first_tool', 'tc_1', {}),
            ('second_tool', 'tc_2', {}),
        ]),
        _text('done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='seq_agent',
        client=client,
        tools=[first_tool, second_tool],
        parallel_tool_execution=False,
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run([{'role': 'user', 'content': 'go'}])

    assert result.text == 'done'
    assert order == ['first', 'second']


@pytest.mark.asyncio
async def test_agent_bounded_concurrency_via_guardrail() -> None:
    """max_concurrent_tools limits simultaneous tool executions."""
    active = 0
    peak = 0

    @tool(description='slow')
    async def slow_a() -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        return 'a'

    @tool(description='slow')
    async def slow_b() -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        return 'b'

    @tool(description='slow')
    async def slow_c() -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        return 'c'

    client = DummyClient([
        _multi_tool([
            ('slow_a', 'tc_1', {}),
            ('slow_b', 'tc_2', {}),
            ('slow_c', 'tc_3', {}),
        ]),
        _text('done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='bounded_agent',
        client=client,
        tools=[slow_a, slow_b, slow_c],
        guardrails=GuardrailConfig(max_concurrent_tools=2),
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run([{'role': 'user', 'content': 'go'}])

    assert result.text == 'done'
    assert peak <= 2


@pytest.mark.asyncio
async def test_sequential_overrides_bounded() -> None:
    """parallel_tool_execution=False takes precedence over max_concurrent_tools."""
    order: list[str] = []

    @tool(description='a')
    async def tool_a() -> str:
        order.append('a')
        return 'a'

    @tool(description='b')
    async def tool_b() -> str:
        order.append('b')
        return 'b'

    client = DummyClient([
        _multi_tool([('tool_a', 'tc_1', {}), ('tool_b', 'tc_2', {})]),
        _text('done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='combo_agent',
        client=client,
        tools=[tool_a, tool_b],
        parallel_tool_execution=False,
        guardrails=GuardrailConfig(max_concurrent_tools=10),
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run([{'role': 'user', 'content': 'go'}])

    assert result.text == 'done'
    assert order == ['a', 'b']


@pytest.mark.asyncio
async def test_single_tool_call_sequential_mode() -> None:
    """Single tool call works correctly in sequential mode."""

    @tool(description='echo')
    def echo(msg: str) -> str:
        return msg

    client = DummyClient([
        _multi_tool([('echo', 'tc_1', {'msg': 'hello'})]),
        _text('done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='single_agent',
        client=client,
        tools=[echo],
        parallel_tool_execution=False,
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run([{'role': 'user', 'content': 'echo hello'}])

    assert result.text == 'done'


@pytest.mark.asyncio
async def test_observability_sequential() -> None:
    """UsageSummary.total_tool_time_ms is populated in sequential mode."""
    from sonya.core.schemas.types import UsageSummary

    @tool(description='slow')
    async def slow() -> str:
        await asyncio.sleep(0.02)
        return 'ok'

    client = DummyClient([
        _multi_tool([('slow', 'tc_1', {})]),
        _text('done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='obs_agent',
        client=client,
        tools=[slow],
        parallel_tool_execution=False,
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run([{'role': 'user', 'content': 'go'}])

    usage: UsageSummary = result.metadata['usage']
    assert usage.total_tool_time_ms >= 0
    assert usage.total_tool_calls == 1


@pytest.mark.asyncio
async def test_stream_sequential_mode() -> None:
    """run_stream also respects parallel_tool_execution=False."""
    order: list[str] = []

    @tool(description='a')
    async def stream_a() -> str:
        order.append('a')
        return 'a'

    @tool(description='b')
    async def stream_b() -> str:
        order.append('b')
        return 'b'

    client = DummyClient([
        _multi_tool([
            ('stream_a', 'tc_1', {}),
            ('stream_b', 'tc_2', {}),
        ]),
        _text('streamed done'),
    ])
    client.__class__.__name__ = 'AnthropicClient'

    agent = Agent(
        name='stream_seq_agent',
        client=client,
        tools=[stream_a, stream_b],
        parallel_tool_execution=False,
    )
    runtime = AgentRuntime(agent)
    final: AgentResult | None = None
    async for item in runtime.run_stream([{'role': 'user', 'content': 'go'}]):
        if isinstance(item, AgentResult):
            final = item

    assert final is not None
    assert final.text == 'streamed done'
    assert order == ['a', 'b']
