"""Tests for DefaultMemoryPipeline.normalize()."""

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.client.memory import DefaultMemoryPipeline


def test_normalize_openai():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]
    result = pipeline.normalize(history, 'openai')
    assert len(result) == 2
    assert result[0] == NormalizedMessage(
        role='user', content='hello'
    )
    assert result[1] == NormalizedMessage(
        role='assistant', content='hi there'
    )


def test_normalize_anthropic_text_blocks():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi '},
                {'type': 'text', 'text': 'there'},
            ],
        },
    ]
    result = pipeline.normalize(history, 'anthropic')
    assert result[1].content == 'hi there'


def test_normalize_anthropic_string_content():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
    ]
    result = pipeline.normalize(history, 'anthropic')
    assert result[0].content == 'hello'


def test_normalize_gemini():
    pipeline = DefaultMemoryPipeline()
    history = [
        {
            'role': 'user',
            'parts': [{'text': 'hello'}],
        },
        {
            'role': 'model',
            'parts': [{'text': 'hi'}, {'text': ' there'}],
        },
    ]
    result = pipeline.normalize(history, 'gemini')
    assert result[0].role == 'user'
    assert result[0].content == 'hello'
    assert result[1].role == 'assistant'
    assert result[1].content == 'hi there'


def test_normalize_unknown_provider_falls_back_to_generic():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'user', 'content': 'hello'},
    ]
    result = pipeline.normalize(history, 'unknown_provider')
    assert result[0].content == 'hello'


def test_normalize_preserves_system_messages():
    pipeline = DefaultMemoryPipeline()
    history = [
        {'role': 'system', 'content': 'You are helpful.'},
        {'role': 'user', 'content': 'hello'},
    ]
    result = pipeline.normalize(history, 'openai')
    assert result[0].role == 'system'
    assert result[0].content == 'You are helpful.'


def test_normalize_empty_history():
    pipeline = DefaultMemoryPipeline()
    result = pipeline.normalize([], 'openai')
    assert result == []
