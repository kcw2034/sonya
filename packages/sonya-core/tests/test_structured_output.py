"""Tests for structured output (output_schema) in AgentRuntime."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.agent import Agent, AgentResult
from sonya.core.client.provider.base import BaseClient
from sonya.core.exceptions.errors import AgentError
from sonya.core.parsers.adapter import (
    AnthropicAdapter,
    OpenAIAdapter,
    GeminiAdapter,
)
from sonya.core.schemas.types import ClientConfig


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


def _text(t: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=t)],
        stop_reason='end_turn',
    )


_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'age': {'type': 'integer'},
    },
    'required': ['name', 'age'],
}


# ---------------------------------------------------------------------------
# Agent.output_schema field
# ---------------------------------------------------------------------------

def test_output_schema_field_default_none() -> None:
    """Agent.output_schema defaults to None."""
    client = _DummyClient([])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    assert agent.output_schema is None


def test_output_schema_field_accepts_dict() -> None:
    """Agent.output_schema accepts a JSON Schema dict."""
    client = _DummyClient([])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client, output_schema=_SCHEMA)
    assert agent.output_schema == _SCHEMA


# ---------------------------------------------------------------------------
# AgentResult.output field
# ---------------------------------------------------------------------------

def test_agent_result_output_default_none() -> None:
    """AgentResult.output defaults to None."""
    result = AgentResult(agent_name='a', text='hi')
    assert result.output is None


def test_agent_result_output_accepts_dict() -> None:
    """AgentResult.output can be set to a parsed dict."""
    result = AgentResult(
        agent_name='a',
        text='{"name": "Alice"}',
        output={'name': 'Alice'},
    )
    assert result.output == {'name': 'Alice'}


# ---------------------------------------------------------------------------
# Runtime: no output_schema → original behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_output_schema_output_is_none() -> None:
    """Without output_schema, result.output is None."""
    client = _DummyClient([_text('hello')])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(name='a', client=client)
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.output is None
    assert result.text == 'hello'


# ---------------------------------------------------------------------------
# Runtime: valid JSON response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_json_parsed_into_output() -> None:
    """Valid JSON response is parsed into result.output."""
    payload = '{"name": "Alice", "age": 30}'
    client = _DummyClient([_text(payload)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a', client=client, output_schema=_SCHEMA
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.output == {'name': 'Alice', 'age': 30}
    assert result.text == payload


# ---------------------------------------------------------------------------
# Runtime: invalid JSON → retry → success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_json_retried_then_succeeds() -> None:
    """Non-JSON first response causes a retry; valid JSON on second succeeds."""
    client = _DummyClient([
        _text('not json at all'),
        _text('{"name": "Bob", "age": 25}'),
    ])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a', client=client, output_schema=_SCHEMA,
        max_iterations=5,
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.output == {'name': 'Bob', 'age': 25}
    assert client._idx == 2


# ---------------------------------------------------------------------------
# Runtime: schema validation fails → retry → success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schema_invalid_retried_then_succeeds() -> None:
    """JSON valid but schema mismatch causes retry."""
    # 'age' is a string, should be integer
    bad = '{"name": "Carol", "age": "thirty"}'
    good = '{"name": "Carol", "age": 30}'
    client = _DummyClient([_text(bad), _text(good)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a', client=client, output_schema=_SCHEMA,
        max_iterations=5,
    )
    result = await AgentRuntime(agent).run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.output == {'name': 'Carol', 'age': 30}


# ---------------------------------------------------------------------------
# Runtime: max_iterations exhausted while retrying
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bad_json_always_exhausts_max_iterations() -> None:
    """Perpetually invalid JSON exhausts max_iterations → AgentError."""
    client = _DummyClient([_text('not json')] * 10)
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a', client=client, output_schema=_SCHEMA,
        max_iterations=3,
    )
    with pytest.raises(AgentError):
        await AgentRuntime(agent).run(
            [{'role': 'user', 'content': 'hi'}]
        )


# ---------------------------------------------------------------------------
# run_stream: structured output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stream_valid_json_output() -> None:
    """run_stream() populates result.output for valid JSON."""
    payload = '{"name": "Dave", "age": 40}'
    client = _DummyClient([_text(payload)])
    client.__class__.__name__ = 'AnthropicClient'
    agent = Agent(
        name='a', client=client, output_schema=_SCHEMA
    )
    result: AgentResult | None = None
    async for item in AgentRuntime(agent).run_stream(
        [{'role': 'user', 'content': 'hi'}]
    ):
        if isinstance(item, AgentResult):
            result = item
    assert result is not None
    assert result.output == {'name': 'Dave', 'age': 40}


# ---------------------------------------------------------------------------
# Adapter: format_generate_kwargs with output_schema
# ---------------------------------------------------------------------------

def test_anthropic_adapter_output_schema_in_system() -> None:
    """Anthropic adapter appends JSON schema hint to system prompt."""
    adapter = AnthropicAdapter()
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}
    kwargs = adapter.format_generate_kwargs(
        'Be helpful.', None, output_schema=schema
    )
    system = kwargs.get('system', '')
    assert 'JSON' in system or 'json' in system


def test_anthropic_adapter_no_output_schema_unchanged() -> None:
    """Anthropic adapter without output_schema leaves system prompt alone."""
    adapter = AnthropicAdapter()
    kwargs = adapter.format_generate_kwargs('Be helpful.', None)
    assert kwargs.get('system') == 'Be helpful.'


def test_openai_adapter_output_schema_adds_response_format() -> None:
    """OpenAI adapter adds response_format with json_schema."""
    adapter = OpenAIAdapter()
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}
    kwargs = adapter.format_generate_kwargs(
        'Be helpful.', None, output_schema=schema
    )
    assert 'response_format' in kwargs
    rf = kwargs['response_format']
    assert rf.get('type') == 'json_schema'


def test_openai_adapter_no_output_schema_no_response_format() -> None:
    """OpenAI adapter without output_schema does not add response_format."""
    adapter = OpenAIAdapter()
    kwargs = adapter.format_generate_kwargs('Be helpful.', None)
    assert 'response_format' not in kwargs


def test_gemini_adapter_output_schema_adds_mime_and_schema() -> None:
    """Gemini adapter adds response_mime_type and response_schema."""
    adapter = GeminiAdapter()
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}
    kwargs = adapter.format_generate_kwargs(
        'Be helpful.', None, output_schema=schema
    )
    assert kwargs.get('response_mime_type') == 'application/json'
    assert kwargs.get('response_schema') == schema


def test_gemini_adapter_no_output_schema_clean() -> None:
    """Gemini adapter without output_schema does not add mime/schema."""
    adapter = GeminiAdapter()
    kwargs = adapter.format_generate_kwargs('Be helpful.', None)
    assert 'response_mime_type' not in kwargs
    assert 'response_schema' not in kwargs
