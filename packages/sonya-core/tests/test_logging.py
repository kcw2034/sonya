"""Tests for the logging system: events, interceptor, and callback."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent
from sonya.core.client.base import BaseClient
from sonya.core.utils.callback import DebugCallback
from sonya.core.schemas.events import (
    AgentEndEvent,
    AgentStartEvent,
    HandoffEvent,
    IterationEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    LogEvent,
    ToolExecutionEvent,
)
from sonya.core.client.interceptor import LoggingInterceptor
from sonya.core.utils.decorator import tool
from sonya.core.schemas.types import ClientConfig


# --- Helpers ---

class DummyClient(BaseClient):
    """A mock client that returns pre-configured responses."""

    def __init__(
        self, responses: list[Any], model: str = 'dummy'
    ) -> None:
        super().__init__(ClientConfig(model=model))
        self._responses = list(responses)
        self._call_count = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        if self._call_count >= len(self._responses):
            raise RuntimeError('No more mock responses')
        response = self._responses[self._call_count]
        self._call_count += 1
        return response

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _make_anthropic_text(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
    )


def _make_anthropic_tool(
    text: str, tool_name: str, tool_id: str,
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


# --- Event dataclass tests ---

class TestEvents:
    """Verify event dataclass creation and immutability."""

    def test_log_event_creation(self) -> None:
        e = LogEvent(event_type='test')
        assert e.event_type == 'test'
        assert e.timestamp > 0

    def test_llm_request_event(self) -> None:
        e = LLMRequestEvent(
            model='gpt-4', message_count=5,
            kwargs_keys=('system',),
        )
        assert e.event_type == 'llm_request'
        assert e.model == 'gpt-4'
        assert e.message_count == 5

    def test_llm_response_event(self) -> None:
        e = LLMResponseEvent(
            model='gpt-4', stop_reason='stop',
            latency_ms=123.4, input_tokens=10,
            output_tokens=20,
        )
        assert e.event_type == 'llm_response'
        assert e.latency_ms == 123.4

    def test_iteration_event(self) -> None:
        e = IterationEvent(
            agent_name='a', iteration=2, phase='start',
        )
        assert e.event_type == 'iteration'
        assert e.phase == 'start'

    def test_tool_execution_event(self) -> None:
        e = ToolExecutionEvent(
            agent_name='a', tool_name='add',
            success=True, duration_ms=12.0,
        )
        assert e.event_type == 'tool_execution'
        assert e.success is True

    def test_handoff_event(self) -> None:
        e = HandoffEvent(from_agent='a', to_agent='b')
        assert e.event_type == 'handoff'

    def test_agent_start_event(self) -> None:
        e = AgentStartEvent(
            agent_name='a', message_count=3,
        )
        assert e.event_type == 'agent_start'

    def test_agent_end_event(self) -> None:
        e = AgentEndEvent(
            agent_name='a', text_preview='hi',
            has_handoff=False,
        )
        assert e.event_type == 'agent_end'

    def test_frozen(self) -> None:
        e = LogEvent(event_type='test')
        with pytest.raises(AttributeError):
            e.event_type = 'other'  # type: ignore[misc]


# --- LoggingInterceptor tests ---

class TestLoggingInterceptor:
    """Verify LoggingInterceptor logs LLM calls."""

    @pytest.mark.asyncio
    async def test_before_request_passthrough(self) -> None:
        interceptor = LoggingInterceptor()
        msgs = [{'role': 'user', 'content': 'hi'}]
        kwargs = {'model': 'test'}
        out_msgs, out_kwargs = await interceptor.before_request(
            msgs, kwargs,
        )
        assert out_msgs is msgs
        assert out_kwargs is kwargs

    @pytest.mark.asyncio
    async def test_after_response_passthrough(self) -> None:
        interceptor = LoggingInterceptor()
        # Simulate before_request first
        await interceptor.before_request([], {'model': 'x'})
        resp = {'result': 'ok'}
        out = await interceptor.after_response(resp)
        assert out is resp

    @pytest.mark.asyncio
    async def test_extract_usage_dict(self) -> None:
        interceptor = LoggingInterceptor()
        resp = {
            'usage': {
                'input_tokens': 100,
                'output_tokens': 50,
            }
        }
        inp, out = interceptor._extract_usage(resp)
        assert inp == 100
        assert out == 50

    @pytest.mark.asyncio
    async def test_extract_usage_object(self) -> None:
        interceptor = LoggingInterceptor()
        resp = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=200,
                output_tokens=80,
            )
        )
        inp, out = interceptor._extract_usage(resp)
        assert inp == 200
        assert out == 80

    @pytest.mark.asyncio
    async def test_extract_stop_reason_dict(self) -> None:
        interceptor = LoggingInterceptor()
        assert interceptor._extract_stop_reason(
            {'stop_reason': 'end'}
        ) == 'end'

    @pytest.mark.asyncio
    async def test_extract_stop_reason_anthropic(self) -> None:
        interceptor = LoggingInterceptor()
        resp = SimpleNamespace(stop_reason='end_turn')
        assert interceptor._extract_stop_reason(resp) == 'end_turn'

    @pytest.mark.asyncio
    async def test_with_client(self, caplog: Any) -> None:
        interceptor = LoggingInterceptor(level=logging.DEBUG)
        client = DummyClient.__new__(DummyClient)
        config = ClientConfig(
            model='test',
            interceptors=[interceptor],
        )
        BaseClient.__init__(client, config)
        client._responses = [{'echo': True}]
        client._call_count = 0

        with caplog.at_level(logging.DEBUG, logger='sonya.client'):
            await client.generate(
                [{'role': 'user', 'content': 'hi'}],
            )

        assert any(
            'LLM Request' in r.message for r in caplog.records
        )
        assert any(
            'LLM Response' in r.message for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_json_mode(self, caplog: Any) -> None:
        interceptor = LoggingInterceptor(
            level=logging.DEBUG, log_json=True,
        )
        client = DummyClient.__new__(DummyClient)
        config = ClientConfig(
            model='dummy',
            interceptors=[interceptor],
        )
        BaseClient.__init__(client, config)
        client._responses = [{'echo': True}]
        client._call_count = 0

        with caplog.at_level(logging.DEBUG, logger='sonya.client'):
            await client.generate(
                [{'role': 'user', 'content': 'hi'}],
            )

        assert any(
            '"event"' in r.message for r in caplog.records
        )


# --- DebugCallback tests ---

class RecordingCallback:
    """Simple callback that records all calls for assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def on_iteration_start(
        self, agent_name: str, iteration: int,
    ) -> None:
        self.calls.append(
            ('iteration_start', (agent_name, iteration))
        )

    async def on_iteration_end(
        self, agent_name: str, iteration: int,
    ) -> None:
        self.calls.append(
            ('iteration_end', (agent_name, iteration))
        )

    async def on_tool_start(
        self, agent_name: str, tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        self.calls.append(
            ('tool_start', (agent_name, tool_name))
        )

    async def on_tool_end(
        self, agent_name: str, tool_name: str,
        arguments: dict[str, Any],
        output: str | None, error: str | None,
        success: bool,
    ) -> None:
        self.calls.append(
            ('tool_end', (agent_name, tool_name, success))
        )

    async def on_handoff(
        self, from_agent: str, to_agent: str,
    ) -> None:
        self.calls.append(
            ('handoff', (from_agent, to_agent))
        )


class TestDebugCallback:
    """Verify DebugCallback logs agent events."""

    @pytest.mark.asyncio
    async def test_simple_response_callbacks(self) -> None:
        """Text-only response fires iteration start/end."""
        recorder = RecordingCallback()
        client = DummyClient(
            [_make_anthropic_text('Hello!')],
        )
        client.__class__.__name__ = 'AnthropicClient'

        agent = Agent(
            name='test',
            client=client,
            callbacks=[recorder],
        )
        runtime = AgentRuntime(agent)
        result = await runtime.run([
            {'role': 'user', 'content': 'Hi'}
        ])

        assert result.text == 'Hello!'
        names = [c[0] for c in recorder.calls]
        assert 'iteration_start' in names
        assert 'iteration_end' in names

    @pytest.mark.asyncio
    async def test_tool_callbacks(self) -> None:
        """Tool use fires tool_start and tool_end callbacks."""

        @tool(description='Add two numbers')
        def add(a: int, b: int) -> int:
            return a + b

        recorder = RecordingCallback()
        client = DummyClient([
            _make_anthropic_tool(
                'Adding', 'add', 'tc_1', {'a': 1, 'b': 2},
            ),
            _make_anthropic_text('Result is 3'),
        ])
        client.__class__.__name__ = 'AnthropicClient'

        agent = Agent(
            name='calc',
            client=client,
            tools=[add],
            callbacks=[recorder],
        )
        runtime = AgentRuntime(agent)
        result = await runtime.run([
            {'role': 'user', 'content': '1+2'}
        ])

        assert result.text == 'Result is 3'
        names = [c[0] for c in recorder.calls]
        assert 'tool_start' in names
        assert 'tool_end' in names
        # Verify order: iteration_start before tool_start
        assert names.index('iteration_start') < (
            names.index('tool_start')
        )

    @pytest.mark.asyncio
    async def test_handoff_callback(self) -> None:
        """Handoff fires on_handoff callback."""
        recorder = RecordingCallback()

        client_a = DummyClient([
            _make_anthropic_tool(
                '', '__handoff_to_b', 'tc_h', {},
            ),
        ])
        client_a.__class__.__name__ = 'AnthropicClient'

        client_b = DummyClient(
            [_make_anthropic_text('Done')],
        )
        client_b.__class__.__name__ = 'AnthropicClient'

        agent_b = Agent(name='b', client=client_b)
        agent_a = Agent(
            name='a',
            client=client_a,
            handoffs=[agent_b],
            callbacks=[recorder],
        )

        runtime = AgentRuntime(agent_a)
        result = await runtime.run([
            {'role': 'user', 'content': 'Go'}
        ])

        assert result.handoff_to == 'b'
        names = [c[0] for c in recorder.calls]
        assert 'handoff' in names

    @pytest.mark.asyncio
    async def test_no_callbacks_unchanged(self) -> None:
        """Agent without callbacks still works normally."""
        client = DummyClient(
            [_make_anthropic_text('OK')],
        )
        client.__class__.__name__ = 'AnthropicClient'

        agent = Agent(name='plain', client=client)
        runtime = AgentRuntime(agent)
        result = await runtime.run([
            {'role': 'user', 'content': 'Hi'}
        ])

        assert result.text == 'OK'
        assert result.agent_name == 'plain'

    @pytest.mark.asyncio
    async def test_debug_callback_logging(
        self, caplog: Any,
    ) -> None:
        """DebugCallback writes to sonya.agent logger."""
        debug = DebugCallback(level=logging.DEBUG)
        client = DummyClient(
            [_make_anthropic_text('Hello')],
        )
        client.__class__.__name__ = 'AnthropicClient'

        agent = Agent(
            name='logged',
            client=client,
            callbacks=[debug],
        )
        runtime = AgentRuntime(agent)

        with caplog.at_level(logging.DEBUG, logger='sonya.agent'):
            await runtime.run([
                {'role': 'user', 'content': 'Hi'}
            ])

        assert any(
            'Iteration Start' in r.message
            for r in caplog.records
        )
        assert any(
            'Iteration End' in r.message
            for r in caplog.records
        )
