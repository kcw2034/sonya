"""Tests for DefaultMemoryPipeline.reconstruct()."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.client.memory import DefaultMemoryPipeline


def _msg(role: str, content: str) -> NormalizedMessage:
    return NormalizedMessage(role=role, content=content)


def test_reconstruct_openai():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    result = pipeline.reconstruct(msgs, 'openai')
    assert result == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]


def test_reconstruct_anthropic():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    result = pipeline.reconstruct(msgs, 'anthropic')
    assert result[0] == {
        'role': 'user',
        'content': [{'type': 'text', 'text': 'hello'}],
    }
    assert result[1] == {
        'role': 'assistant',
        'content': [{'type': 'text', 'text': 'hi'}],
    }


def test_reconstruct_gemini():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello'), _msg('assistant', 'hi')]
    result = pipeline.reconstruct(msgs, 'gemini')
    assert result[0] == {
        'role': 'user',
        'parts': [{'text': 'hello'}],
    }
    assert result[1] == {
        'role': 'model',
        'parts': [{'text': 'hi'}],
    }


def test_reconstruct_gemini_system_role():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('system', 'Be helpful.')]
    result = pipeline.reconstruct(msgs, 'gemini')
    assert result[0]['role'] == 'user'


def test_reconstruct_unknown_provider():
    pipeline = DefaultMemoryPipeline()
    msgs = [_msg('user', 'hello')]
    result = pipeline.reconstruct(msgs, 'unknown')
    assert result == [{'role': 'user', 'content': 'hello'}]


def test_reconstruct_empty():
    pipeline = DefaultMemoryPipeline()
    result = pipeline.reconstruct([], 'openai')
    assert result == []


def test_roundtrip_openai():
    pipeline = DefaultMemoryPipeline()
    original = [
        {'role': 'system', 'content': 'You are helpful.'},
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
    normalized = pipeline.normalize(original, 'openai')
    restored = pipeline.reconstruct(normalized, 'openai')
    assert restored == original


def test_roundtrip_cross_provider():
    pipeline = DefaultMemoryPipeline()
    anthropic_history = [
        {'role': 'user', 'content': 'hello'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi there'},
            ],
        },
    ]
    normalized = pipeline.normalize(
        anthropic_history, 'anthropic'
    )
    openai_history = pipeline.reconstruct(
        normalized, 'openai'
    )
    assert openai_history == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
