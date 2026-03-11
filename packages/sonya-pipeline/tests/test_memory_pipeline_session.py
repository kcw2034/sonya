"""Tests for DefaultMemoryPipeline session methods."""

import pytest

from sonya.core.schemas.memory import NormalizedMessage
from sonya.pipeline.client.memory import DefaultMemoryPipeline
from sonya.pipeline.stores.in_memory import InMemoryStore


def test_save_and_load_session():
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())
    history = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]
    pipeline.save_session('s1', history, 'openai')
    result = pipeline.load_session('s1', 'openai')
    assert result == history


def test_load_session_cross_provider():
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())
    anthropic_history = [
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi'},
            ],
        },
    ]
    pipeline.save_session('s1', anthropic_history, 'anthropic')
    result = pipeline.load_session('s1', 'openai')
    assert result == [
        {'role': 'assistant', 'content': 'hi'},
    ]


def test_load_session_last_n():
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())
    history = [
        {'role': 'user', 'content': f'm{i}'}
        for i in range(5)
    ]
    pipeline.save_session('s1', history, 'openai')
    result = pipeline.load_session('s1', 'openai', last_n=2)
    assert len(result) == 2


def test_save_session_without_store_raises():
    pipeline = DefaultMemoryPipeline()
    with pytest.raises(ValueError, match='No store configured'):
        pipeline.save_session('s1', [], 'openai')


def test_load_session_without_store_raises():
    pipeline = DefaultMemoryPipeline()
    with pytest.raises(ValueError, match='No store configured'):
        pipeline.load_session('s1', 'openai')


def test_satisfies_memory_pipeline_protocol():
    from sonya.core.schemas.memory import MemoryPipeline
    assert isinstance(DefaultMemoryPipeline(), MemoryPipeline)
