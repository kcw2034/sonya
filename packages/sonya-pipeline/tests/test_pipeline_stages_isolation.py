"""Isolated unit tests for Pipeline.stages and individual stage
process() methods: FilterByRoleStage, MetadataInjectionStage,
TruncateStage (edge cases), and SystemPromptStage (edge cases)."""

from __future__ import annotations

from sonya.pipeline.client.pipeline import (
    FilterByRoleStage,
    MetadataInjectionStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)


# ── Pipeline.stages property ─────────────────────────────────────────────

def test_stages_empty_on_new_pipeline() -> None:
    p = Pipeline()
    assert p.stages == []


def test_stages_returns_registered_stages_in_order() -> None:
    p = Pipeline()
    s1 = TruncateStage(max_turns=5)
    s2 = FilterByRoleStage()
    p.add_stage(s1).add_stage(s2)
    stages = p.stages
    assert stages[0] is s1
    assert stages[1] is s2


def test_stages_returns_copy_not_internal_list() -> None:
    """Mutating the returned list must not affect the pipeline."""
    p = Pipeline()
    p.add_stage(TruncateStage(max_turns=3))
    stages = p.stages
    stages.clear()
    assert len(p.stages) == 1


# ── FilterByRoleStage.process ────────────────────────────────────────────

def test_filter_keeps_default_roles() -> None:
    stage = FilterByRoleStage()
    msgs = [
        {'role': 'system', 'content': 'sys'},
        {'role': 'user', 'content': 'hello'},
        {'role': 'assistant', 'content': 'hi'},
    ]
    result = stage.process(msgs)
    roles = [m['role'] for m in result]
    assert roles == ['user', 'assistant']


def test_filter_with_custom_roles() -> None:
    stage = FilterByRoleStage(roles=('system', 'user'))
    msgs = [
        {'role': 'system', 'content': 's'},
        {'role': 'user', 'content': 'u'},
        {'role': 'assistant', 'content': 'a'},
    ]
    result = stage.process(msgs)
    assert all(m['role'] in ('system', 'user') for m in result)
    assert len(result) == 2


def test_filter_empty_input_returns_empty() -> None:
    stage = FilterByRoleStage()
    assert stage.process([]) == []


def test_filter_all_excluded_returns_empty() -> None:
    stage = FilterByRoleStage(roles=('user',))
    msgs = [
        {'role': 'system', 'content': 's'},
        {'role': 'assistant', 'content': 'a'},
    ]
    assert stage.process(msgs) == []


def test_filter_preserves_message_content() -> None:
    stage = FilterByRoleStage(roles=('user',))
    msg = {'role': 'user', 'content': 'keep me', 'extra': 'data'}
    result = stage.process([msg])
    assert result[0]['content'] == 'keep me'
    assert result[0]['extra'] == 'data'


# ── MetadataInjectionStage.process ───────────────────────────────────────

def test_metadata_injects_new_keys() -> None:
    stage = MetadataInjectionStage(
        metadata={'source': 'pipeline', 'version': '1'}
    )
    msgs = [{'role': 'user', 'content': 'hi'}]
    result = stage.process(msgs)
    assert result[0]['source'] == 'pipeline'
    assert result[0]['version'] == '1'


def test_metadata_does_not_overwrite_existing_keys() -> None:
    stage = MetadataInjectionStage(
        metadata={'role': 'injected', 'tag': 'new'}
    )
    msgs = [{'role': 'user', 'content': 'hi'}]
    result = stage.process(msgs)
    # 'role' already exists — setdefault must not overwrite it
    assert result[0]['role'] == 'user'
    assert result[0]['tag'] == 'new'


def test_metadata_empty_dict_is_noop() -> None:
    stage = MetadataInjectionStage(metadata={})
    msgs = [{'role': 'user', 'content': 'hi'}]
    result = stage.process(msgs)
    assert result == msgs


def test_metadata_applied_to_all_messages() -> None:
    stage = MetadataInjectionStage(metadata={'env': 'test'})
    msgs = [
        {'role': 'user', 'content': 'a'},
        {'role': 'assistant', 'content': 'b'},
    ]
    result = stage.process(msgs)
    assert all(m['env'] == 'test' for m in result)


def test_metadata_does_not_mutate_original_messages() -> None:
    stage = MetadataInjectionStage(metadata={'tag': 'x'})
    original = {'role': 'user', 'content': 'hi'}
    msgs = [original]
    stage.process(msgs)
    assert 'tag' not in original


def test_metadata_empty_input_returns_empty() -> None:
    stage = MetadataInjectionStage(metadata={'k': 'v'})
    assert stage.process([]) == []


# ── TruncateStage edge cases ─────────────────────────────────────────────

def test_truncate_preserves_system_messages() -> None:
    stage = TruncateStage(max_turns=1)
    msgs = [
        {'role': 'system', 'content': 'sys'},
        {'role': 'user', 'content': 'first'},
        {'role': 'user', 'content': 'second'},
    ]
    result = stage.process(msgs)
    roles = [m['role'] for m in result]
    assert roles[0] == 'system'
    assert result[-1]['content'] == 'second'


def test_truncate_max_turns_larger_than_history() -> None:
    stage = TruncateStage(max_turns=100)
    msgs = [
        {'role': 'user', 'content': 'a'},
        {'role': 'assistant', 'content': 'b'},
    ]
    result = stage.process(msgs)
    assert len(result) == 2


def test_truncate_empty_input_returns_empty() -> None:
    stage = TruncateStage(max_turns=5)
    assert stage.process([]) == []


def test_truncate_only_system_messages_unchanged() -> None:
    stage = TruncateStage(max_turns=2)
    msgs = [
        {'role': 'system', 'content': 'a'},
        {'role': 'system', 'content': 'b'},
    ]
    result = stage.process(msgs)
    assert len(result) == 2


# ── SystemPromptStage edge cases ─────────────────────────────────────────

def test_system_prompt_replaces_existing_system_message() -> None:
    stage = SystemPromptStage(prompt='new prompt')
    msgs = [
        {'role': 'system', 'content': 'old'},
        {'role': 'user', 'content': 'hi'},
    ]
    result = stage.process(msgs)
    system_msgs = [m for m in result if m['role'] == 'system']
    assert len(system_msgs) == 1
    assert system_msgs[0]['content'] == 'new prompt'


def test_system_prompt_adds_when_none_present() -> None:
    stage = SystemPromptStage(prompt='injected')
    msgs = [{'role': 'user', 'content': 'hi'}]
    result = stage.process(msgs)
    assert result[0] == {'role': 'system', 'content': 'injected'}


def test_system_prompt_appears_first() -> None:
    stage = SystemPromptStage(prompt='first')
    msgs = [{'role': 'user', 'content': 'u'}]
    result = stage.process(msgs)
    assert result[0]['role'] == 'system'


def test_system_prompt_empty_input_adds_system_only() -> None:
    stage = SystemPromptStage(prompt='sys')
    result = stage.process([])
    assert result == [{'role': 'system', 'content': 'sys'}]
