"""Tests for Observability — token aggregation and execution metrics."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.client.base import BaseClient
from sonya.core.schemas.types import ClientConfig, UsageSummary
from sonya.core.utils.decorator import tool
from sonya.core.client.provider.interceptor import extract_usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyClient(BaseClient):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__(ClientConfig(model='dummy'))
        self._responses = list(responses)
        self._idx = 0

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        resp = self._responses[self._idx]
        self._idx += 1
        return resp

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        yield await self._provider_generate(messages, **kwargs)


def _anthropic_resp(
    text: str,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> SimpleNamespace:
    """Simulate an Anthropic-style response with usage."""
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        stop_reason='end_turn',
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )


def _openai_resp(
    text: str,
    prompt_tokens: int = 8,
    completion_tokens: int = 4,
) -> SimpleNamespace:
    """Simulate an OpenAI-style response with usage."""
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=text, tool_calls=None),
            finish_reason='stop',
        )],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def _tool_call_resp(name: str, call_id: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type='tool_use',
                id=call_id,
                name=name,
                input=args,
            )
        ],
        stop_reason='tool_use',
        usage=SimpleNamespace(input_tokens=15, output_tokens=3),
    )


@tool(description='Simple echo tool')
async def _echo(msg: str) -> str:
    return msg


# ---------------------------------------------------------------------------
# extract_usage utility function
# ---------------------------------------------------------------------------

def test_extract_usage_anthropic_style() -> None:
    """extract_usage handles Anthropic .usage.input_tokens."""
    resp = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=20, output_tokens=10)
    )
    inp, out = extract_usage(resp)
    assert inp == 20
    assert out == 10


def test_extract_usage_openai_style() -> None:
    """extract_usage handles OpenAI .usage.prompt_tokens."""
    resp = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=15, completion_tokens=7)
    )
    inp, out = extract_usage(resp)
    assert inp == 15
    assert out == 7


def test_extract_usage_gemini_style() -> None:
    """extract_usage handles Gemini .usage_metadata."""
    resp = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=12,
            candidates_token_count=6,
        )
    )
    inp, out = extract_usage(resp)
    assert inp == 12
    assert out == 6


def test_extract_usage_no_usage_returns_zeros() -> None:
    """extract_usage returns (0, 0) when no usage info is present."""
    resp = SimpleNamespace(content='hello')
    inp, out = extract_usage(resp)
    assert inp == 0
    assert out == 0


def test_extract_usage_dict_fallback() -> None:
    """extract_usage handles dict-format response."""
    resp = {'usage': {'input_tokens': 5, 'output_tokens': 3}}
    inp, out = extract_usage(resp)
    assert inp == 5
    assert out == 3


# ---------------------------------------------------------------------------
# UsageSummary field
# ---------------------------------------------------------------------------

def test_usage_summary_defaults() -> None:
    """UsageSummary has correct zero defaults."""
    s = UsageSummary()
    assert s.total_input_tokens == 0
    assert s.total_output_tokens == 0
    assert s.llm_calls == 0
    assert s.iterations == 0
    assert s.total_tool_calls == 0
    assert s.total_tool_time_ms == 0.0
    assert s.total_latency_ms == 0.0


# ---------------------------------------------------------------------------
# AgentResult.metadata['usage'] — single iteration, no tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metadata_usage_populated_after_run() -> None:
    """result.metadata['usage'] is a UsageSummary after run()."""
    client = _DummyClient([_anthropic_resp('hello', 10, 5)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert 'usage' in result.metadata
    usage = result.metadata['usage']
    assert isinstance(usage, UsageSummary)


@pytest.mark.asyncio
async def test_single_llm_call_metrics() -> None:
    """Single text response → llm_calls=1, iterations=1, no tools."""
    client = _DummyClient([_anthropic_resp('hello', 10, 5)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    usage: UsageSummary = result.metadata['usage']
    assert usage.llm_calls == 1
    assert usage.iterations == 1
    assert usage.total_tool_calls == 0
    assert usage.total_tool_time_ms == 0.0


@pytest.mark.asyncio
async def test_token_aggregation_anthropic() -> None:
    """Anthropic-style token usage is aggregated in metadata."""
    client = _DummyClient([_anthropic_resp('hello', 20, 8)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    usage: UsageSummary = result.metadata['usage']
    assert usage.total_input_tokens == 20
    assert usage.total_output_tokens == 8


@pytest.mark.asyncio
async def test_token_aggregation_openai() -> None:
    """OpenAI-style token usage (prompt/completion) is aggregated."""
    client = _DummyClient([_openai_resp('hello', 15, 6)])
    client.__class__.__name__ = 'OpenAIClient'
    agent = Agent(name='a', client=client)
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    usage: UsageSummary = result.metadata['usage']
    assert usage.total_input_tokens == 15
    assert usage.total_output_tokens == 6


# ---------------------------------------------------------------------------
# Multi-iteration (tool call) metrics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_call_metrics() -> None:
    """Tool call run → llm_calls=2, iterations=2, total_tool_calls=1."""
    tool_resp = _tool_call_resp('_echo', 'c1', {'msg': 'hi'})
    final_resp = _anthropic_resp('done', 5, 2)
    client = _DummyClient([tool_resp, final_resp])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client, tools=[_echo])
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    usage: UsageSummary = result.metadata['usage']
    assert usage.llm_calls == 2
    assert usage.iterations == 2
    assert usage.total_tool_calls == 1
    assert usage.total_tool_time_ms >= 0.0


@pytest.mark.asyncio
async def test_token_accumulation_across_iterations() -> None:
    """Tokens from multiple LLM calls are summed."""
    tool_resp = _tool_call_resp('_echo', 'c1', {'msg': 'hi'})
    # tool_resp usage: input=15, output=3
    final_resp = _anthropic_resp('done', 5, 2)
    # final_resp usage: input=5, output=2
    client = _DummyClient([tool_resp, final_resp])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client, tools=[_echo])
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'go'}]
    )
    usage: UsageSummary = result.metadata['usage']
    assert usage.total_input_tokens == 20   # 15 + 5
    assert usage.total_output_tokens == 5   # 3 + 2


# ---------------------------------------------------------------------------
# run_stream: metadata usage also populated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stream_usage_populated() -> None:
    """run_stream final AgentResult also has metadata['usage']."""
    client = _DummyClient([_anthropic_resp('hello', 12, 4)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    result: AgentResult | None = None
    async for item in AgentRuntime(agent).run_stream(
        [{'role': 'user', 'content': 'hi'}]
    ):
        if isinstance(item, AgentResult):
            result = item
    assert result is not None
    assert 'usage' in result.metadata
    usage: UsageSummary = result.metadata['usage']
    assert isinstance(usage, UsageSummary)
    assert usage.total_input_tokens == 12
    assert usage.total_output_tokens == 4
    assert usage.llm_calls == 1


# ---------------------------------------------------------------------------
# UsageSummary importable from sonya.core
# ---------------------------------------------------------------------------

def test_usage_summary_importable_from_sonya_core() -> None:
    """UsageSummary is importable from sonya.core."""
    from sonya.core import UsageSummary as US
    s = US(total_input_tokens=5)
    assert s.total_input_tokens == 5
