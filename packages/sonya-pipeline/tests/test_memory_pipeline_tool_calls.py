"""Tests for tool_calls/tool_results support in DefaultMemoryPipeline."""

from __future__ import annotations

from typing import Any

import pytest

from sonya.pipeline.client.memory import DefaultMemoryPipeline
from sonya.core.schemas.memory import NormalizedMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pipeline = DefaultMemoryPipeline()


def _find(
    msgs: list[NormalizedMessage],
    role: str,
) -> NormalizedMessage | None:
    for m in msgs:
        if m.role == role:
            return m
    return None


# ---------------------------------------------------------------------------
# Anthropic normalize — tool_use and tool_result blocks
# ---------------------------------------------------------------------------

def test_normalize_anthropic_tool_use() -> None:
    """Anthropic tool_use block is extracted into tool_calls."""
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'Let me search.'},
                {
                    'type': 'tool_use',
                    'id': 'tc_1',
                    'name': 'search',
                    'input': {'q': 'test'},
                },
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'anthropic')
    assert len(normalized) == 1
    msg = normalized[0]
    assert msg.role == 'assistant'
    assert msg.content == 'Let me search.'
    assert len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert tc['id'] == 'tc_1'
    assert tc['name'] == 'search'
    assert tc['arguments'] == {'q': 'test'}


def test_normalize_anthropic_tool_result() -> None:
    """Anthropic tool_result block is extracted into tool_results."""
    history: list[dict[str, Any]] = [
        {
            'role': 'user',
            'content': [
                {
                    'type': 'tool_result',
                    'tool_use_id': 'tc_1',
                    'content': 'search result here',
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'anthropic')
    assert len(normalized) == 1
    msg = normalized[0]
    assert msg.role == 'user'
    assert len(msg.tool_results) == 1
    tr = msg.tool_results[0]
    assert tr['call_id'] == 'tc_1'
    assert tr['output'] == 'search result here'


def test_normalize_anthropic_mixed_content() -> None:
    """Anthropic message with both text and tool_use is handled."""
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'Thinking...'},
                {
                    'type': 'tool_use',
                    'id': 'tc_2',
                    'name': 'calc',
                    'input': {'x': 5},
                },
                {'type': 'text', 'text': ' done.'},
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'anthropic')
    msg = normalized[0]
    assert msg.content == 'Thinking... done.'
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0]['name'] == 'calc'


# ---------------------------------------------------------------------------
# OpenAI normalize — tool_calls array and role='tool'
# ---------------------------------------------------------------------------

def test_normalize_openai_tool_calls() -> None:
    """OpenAI tool_calls array is extracted into tool_calls."""
    import json
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': '',
            'tool_calls': [
                {
                    'id': 'tc_1',
                    'type': 'function',
                    'function': {
                        'name': 'search',
                        'arguments': json.dumps({'q': 'test'}),
                    },
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'openai')
    assert len(normalized) == 1
    msg = normalized[0]
    assert msg.role == 'assistant'
    assert len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert tc['id'] == 'tc_1'
    assert tc['name'] == 'search'
    assert tc['arguments'] == {'q': 'test'}


def test_normalize_openai_tool_role_message() -> None:
    """OpenAI role='tool' message is extracted into tool_results."""
    history: list[dict[str, Any]] = [
        {
            'role': 'tool',
            'tool_call_id': 'tc_1',
            'content': 'result data',
        }
    ]
    normalized = pipeline.normalize(history, 'openai')
    assert len(normalized) == 1
    msg = normalized[0]
    assert msg.role == 'tool'
    assert len(msg.tool_results) == 1
    tr = msg.tool_results[0]
    assert tr['call_id'] == 'tc_1'
    assert tr['output'] == 'result data'


def test_normalize_openai_tool_calls_args_already_dict() -> None:
    """OpenAI tool call with dict arguments (not JSON string) is handled."""
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': None,
            'tool_calls': [
                {
                    'id': 'tc_2',
                    'type': 'function',
                    'function': {
                        'name': 'fetch',
                        'arguments': {'url': 'http://example.com'},
                    },
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'openai')
    msg = normalized[0]
    assert msg.tool_calls[0]['arguments'] == {'url': 'http://example.com'}


# ---------------------------------------------------------------------------
# Gemini normalize — function_call and function_response
# ---------------------------------------------------------------------------

def test_normalize_gemini_function_call() -> None:
    """Gemini function_call part is extracted into tool_calls."""
    history: list[dict[str, Any]] = [
        {
            'role': 'model',
            'parts': [
                {
                    'function_call': {
                        'name': 'search',
                        'args': {'q': 'test'},
                    }
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'gemini')
    assert len(normalized) == 1
    msg = normalized[0]
    assert msg.role == 'assistant'
    assert len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert tc['name'] == 'search'
    assert tc['arguments'] == {'q': 'test'}
    # Gemini has no native ID — synthetic one is assigned
    assert 'id' in tc


def test_normalize_gemini_function_response() -> None:
    """Gemini function_response part is extracted into tool_results."""
    history: list[dict[str, Any]] = [
        {
            'role': 'user',
            'parts': [
                {
                    'function_response': {
                        'name': 'search',
                        'response': {'result': 'found it'},
                    }
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'gemini')
    assert len(normalized) == 1
    msg = normalized[0]
    assert len(msg.tool_results) == 1
    tr = msg.tool_results[0]
    assert tr['name'] == 'search'
    assert tr['output'] == 'found it'


# ---------------------------------------------------------------------------
# No tool_calls — backward compatible
# ---------------------------------------------------------------------------

def test_normalize_no_tool_calls_backward_compat() -> None:
    """Plain text messages still normalize with empty tool_calls/tool_results."""
    history: list[dict[str, Any]] = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
    for provider in ('anthropic', 'openai', 'gemini', 'generic'):
        normalized = pipeline.normalize(history, provider)
        for msg in normalized:
            assert msg.tool_calls == []
            assert msg.tool_results == []


# ---------------------------------------------------------------------------
# Reconstruct — Anthropic
# ---------------------------------------------------------------------------

def test_reconstruct_anthropic_tool_use() -> None:
    """NormalizedMessage with tool_calls reconstructs tool_use block."""
    msgs = [
        NormalizedMessage(
            role='assistant',
            content='Let me search.',
            tool_calls=[
                {'id': 'tc_1', 'name': 'search', 'arguments': {'q': 'x'}}
            ],
        )
    ]
    result = pipeline.reconstruct(msgs, 'anthropic')
    assert len(result) == 1
    content = result[0]['content']
    assert isinstance(content, list)
    types = [b['type'] for b in content]
    assert 'text' in types
    assert 'tool_use' in types
    tool_use = next(b for b in content if b['type'] == 'tool_use')
    assert tool_use['id'] == 'tc_1'
    assert tool_use['name'] == 'search'
    assert tool_use['input'] == {'q': 'x'}


def test_reconstruct_anthropic_tool_result() -> None:
    """NormalizedMessage with tool_results reconstructs tool_result block."""
    msgs = [
        NormalizedMessage(
            role='user',
            content='',
            tool_results=[
                {'call_id': 'tc_1', 'output': 'found it', 'name': 'search'}
            ],
        )
    ]
    result = pipeline.reconstruct(msgs, 'anthropic')
    assert len(result) == 1
    content = result[0]['content']
    assert isinstance(content, list)
    tool_result = next(
        b for b in content if b.get('type') == 'tool_result'
    )
    assert tool_result['tool_use_id'] == 'tc_1'
    assert tool_result['content'] == 'found it'


# ---------------------------------------------------------------------------
# Reconstruct — OpenAI
# ---------------------------------------------------------------------------

def test_reconstruct_openai_tool_calls() -> None:
    """NormalizedMessage with tool_calls reconstructs OpenAI tool_calls."""
    import json
    msgs = [
        NormalizedMessage(
            role='assistant',
            content='',
            tool_calls=[
                {'id': 'tc_1', 'name': 'search', 'arguments': {'q': 'x'}}
            ],
        )
    ]
    result = pipeline.reconstruct(msgs, 'openai')
    assert len(result) == 1
    msg = result[0]
    assert 'tool_calls' in msg
    tc = msg['tool_calls'][0]
    assert tc['id'] == 'tc_1'
    assert tc['type'] == 'function'
    assert tc['function']['name'] == 'search'
    args = tc['function']['arguments']
    if isinstance(args, str):
        args = json.loads(args)
    assert args == {'q': 'x'}


def test_reconstruct_openai_tool_results() -> None:
    """NormalizedMessage with tool_results reconstructs role='tool' message."""
    msgs = [
        NormalizedMessage(
            role='tool',
            content='result data',
            tool_results=[
                {'call_id': 'tc_1', 'output': 'result data', 'name': 'search'}
            ],
        )
    ]
    result = pipeline.reconstruct(msgs, 'openai')
    assert len(result) == 1
    msg = result[0]
    assert msg['role'] == 'tool'
    assert msg['tool_call_id'] == 'tc_1'


# ---------------------------------------------------------------------------
# Reconstruct — Gemini
# ---------------------------------------------------------------------------

def test_reconstruct_gemini_function_call() -> None:
    """NormalizedMessage with tool_calls reconstructs Gemini function_call."""
    msgs = [
        NormalizedMessage(
            role='assistant',
            content='',
            tool_calls=[
                {
                    'id': 'gemini_call_0',
                    'name': 'search',
                    'arguments': {'q': 'test'},
                }
            ],
        )
    ]
    result = pipeline.reconstruct(msgs, 'gemini')
    assert len(result) == 1
    parts = result[0]['parts']
    fc_parts = [p for p in parts if 'function_call' in p]
    assert len(fc_parts) == 1
    assert fc_parts[0]['function_call']['name'] == 'search'


def test_reconstruct_gemini_function_response() -> None:
    """NormalizedMessage with tool_results reconstructs Gemini function_response."""
    msgs = [
        NormalizedMessage(
            role='user',
            content='',
            tool_results=[
                {
                    'call_id': 'tc_1',
                    'name': 'search',
                    'output': 'result',
                }
            ],
        )
    ]
    result = pipeline.reconstruct(msgs, 'gemini')
    assert len(result) == 1
    parts = result[0]['parts']
    fr_parts = [p for p in parts if 'function_response' in p]
    assert len(fr_parts) == 1
    assert fr_parts[0]['function_response']['name'] == 'search'


# ---------------------------------------------------------------------------
# Roundtrip — same provider
# ---------------------------------------------------------------------------

def test_roundtrip_anthropic() -> None:
    """Anthropic tool_use → normalize → reconstruct is lossless."""
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'Calling tool.'},
                {
                    'type': 'tool_use',
                    'id': 'tc_rt',
                    'name': 'calc',
                    'input': {'x': 10},
                },
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'anthropic')
    reconstructed = pipeline.reconstruct(normalized, 'anthropic')
    content = reconstructed[0]['content']
    assert isinstance(content, list)
    tu = next(b for b in content if b.get('type') == 'tool_use')
    assert tu['id'] == 'tc_rt'
    assert tu['name'] == 'calc'
    assert tu['input'] == {'x': 10}


def test_roundtrip_openai() -> None:
    """OpenAI tool_calls → normalize → reconstruct is lossless."""
    import json
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': '',
            'tool_calls': [
                {
                    'id': 'tc_rt',
                    'type': 'function',
                    'function': {
                        'name': 'add',
                        'arguments': json.dumps({'a': 1, 'b': 2}),
                    },
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'openai')
    reconstructed = pipeline.reconstruct(normalized, 'openai')
    tc = reconstructed[0]['tool_calls'][0]
    assert tc['id'] == 'tc_rt'
    args = tc['function']['arguments']
    if isinstance(args, str):
        args = json.loads(args)
    assert args == {'a': 1, 'b': 2}


# ---------------------------------------------------------------------------
# Cross-provider conversion
# ---------------------------------------------------------------------------

def test_cross_provider_anthropic_to_openai() -> None:
    """Anthropic tool_use → normalize → reconstruct as OpenAI."""
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': [
                {
                    'type': 'tool_use',
                    'id': 'tc_cross',
                    'name': 'search',
                    'input': {'q': 'py'},
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'anthropic')
    result = pipeline.reconstruct(normalized, 'openai')
    msg = result[0]
    assert 'tool_calls' in msg
    tc = msg['tool_calls'][0]
    assert tc['id'] == 'tc_cross'
    assert tc['function']['name'] == 'search'


def test_cross_provider_openai_to_anthropic() -> None:
    """OpenAI tool_calls → normalize → reconstruct as Anthropic."""
    import json
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': '',
            'tool_calls': [
                {
                    'id': 'tc_cross',
                    'type': 'function',
                    'function': {
                        'name': 'fetch',
                        'arguments': json.dumps({'url': 'http://x.com'}),
                    },
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'openai')
    result = pipeline.reconstruct(normalized, 'anthropic')
    content = result[0]['content']
    tu = next(b for b in content if b.get('type') == 'tool_use')
    assert tu['id'] == 'tc_cross'
    assert tu['name'] == 'fetch'


def test_cross_provider_openai_to_gemini() -> None:
    """OpenAI tool_calls → normalize → reconstruct as Gemini."""
    import json
    history: list[dict[str, Any]] = [
        {
            'role': 'assistant',
            'content': None,
            'tool_calls': [
                {
                    'id': 'tc_g',
                    'type': 'function',
                    'function': {
                        'name': 'greet',
                        'arguments': json.dumps({'name': 'Alice'}),
                    },
                }
            ],
        }
    ]
    normalized = pipeline.normalize(history, 'openai')
    result = pipeline.reconstruct(normalized, 'gemini')
    parts = result[0]['parts']
    fc_parts = [p for p in parts if 'function_call' in p]
    assert fc_parts[0]['function_call']['name'] == 'greet'
