"""Integration tests for the full memory pipeline flow."""

from sonya.core.schemas.memory import MemoryPipeline, NormalizedMessage
from sonya.pipeline import (
    DefaultMemoryPipeline,
    InMemoryStore,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)


def test_protocol_compliance():
    """DefaultMemoryPipeline satisfies sonya-core MemoryPipeline."""
    pipeline = DefaultMemoryPipeline()
    assert isinstance(pipeline, MemoryPipeline)


def test_cross_provider_anthropic_to_openai():
    """Full normalize + reconstruct: Anthropic -> OpenAI."""
    pipeline = DefaultMemoryPipeline()
    anthropic_history = [
        {'role': 'user', 'content': 'Summarize this.'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'Here is the summary.'},
            ],
        },
    ]
    normalized = pipeline.normalize(
        anthropic_history, 'anthropic'
    )
    openai_history = pipeline.reconstruct(normalized, 'openai')
    assert openai_history == [
        {'role': 'user', 'content': 'Summarize this.'},
        {'role': 'assistant', 'content': 'Here is the summary.'},
    ]


def test_cross_provider_openai_to_gemini():
    """Full normalize + reconstruct: OpenAI -> Gemini."""
    pipeline = DefaultMemoryPipeline()
    openai_history = [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]
    normalized = pipeline.normalize(openai_history, 'openai')
    gemini_history = pipeline.reconstruct(normalized, 'gemini')
    assert gemini_history == [
        {'role': 'user', 'parts': [{'text': 'hello'}]},
        {'role': 'model', 'parts': [{'text': 'hi'}]},
    ]


def test_session_memory_with_in_memory_store():
    """Save and load session via InMemoryStore."""
    pipeline = DefaultMemoryPipeline(store=InMemoryStore())

    # Save Anthropic conversation
    pipeline.save_session('s1', [
        {'role': 'user', 'content': 'hello'},
        {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': 'hi there'},
            ],
        },
    ], 'anthropic')

    # Load as OpenAI format
    result = pipeline.load_session('s1', 'openai')
    assert result == [
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi there'},
    ]


def test_memory_with_pipeline_stages_composition():
    """Memory pipeline + Pipeline stages used independently."""
    memory = DefaultMemoryPipeline(store=InMemoryStore())

    # Save conversation
    memory.save_session('s1', [
        {'role': 'user', 'content': f'msg{i}'}
        for i in range(10)
    ], 'openai')

    # Load and transform through Pipeline stages
    messages = memory.load_session('s1', 'openai')
    pipeline = Pipeline()
    pipeline.add_stage(
        SystemPromptStage('You are a helpful assistant.')
    )
    pipeline.add_stage(TruncateStage(max_turns=3))
    result = pipeline.run(messages)

    # System prompt + last 3 messages
    assert len(result) == 4
    assert result[0]['role'] == 'system'
    assert result[1]['content'] == 'msg7'
