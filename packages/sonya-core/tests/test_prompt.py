"""Tests for Prompt and Example data types."""

from unittest.mock import MagicMock

from sonya.core.models.agent import Agent
from sonya.core.models.prompt import Example, Prompt


def test_example_creation():
    ex = Example(user='Hello', assistant='Hi there')
    assert ex.user == 'Hello'
    assert ex.assistant == 'Hi there'


def test_example_is_frozen():
    ex = Example(user='a', assistant='b')
    try:
        ex.user = 'c'
        assert False, 'Should have raised'
    except AttributeError:
        pass


def test_example_equality():
    a = Example(user='x', assistant='y')
    b = Example(user='x', assistant='y')
    assert a == b


def test_prompt_defaults():
    p = Prompt()
    assert p.role == ''
    assert p.guidelines == ()
    assert p.constraints == ()
    assert p.examples == ()
    assert p.output_format == ''


def test_prompt_is_frozen():
    p = Prompt(role='test')
    try:
        p.role = 'changed'
        assert False, 'Should have raised'
    except AttributeError:
        pass


def test_prompt_render_role_only():
    p = Prompt(role='You are a helpful assistant.')
    result = p.render()
    assert result == 'You are a helpful assistant.'


def test_prompt_render_all_sections():
    p = Prompt(
        role='You are an expert.',
        guidelines=('Be concise.', 'Use tools.'),
        constraints=('No fabrication.',),
        examples=(
            Example(user='Hi', assistant='Hello!'),
        ),
        output_format='Respond in JSON.',
    )
    result = p.render()
    assert 'You are an expert.' in result
    assert '## Guidelines' in result
    assert '- Be concise.' in result
    assert '- Use tools.' in result
    assert '## Constraints' in result
    assert '- No fabrication.' in result
    assert '## Examples' in result
    assert 'User: Hi' in result
    assert 'Assistant: Hello!' in result
    assert '## Output Format' in result
    assert 'Respond in JSON.' in result


def test_prompt_render_skips_empty_sections():
    p = Prompt(
        role='You are a bot.',
        guidelines=('Be nice.',),
    )
    result = p.render()
    assert '## Guidelines' in result
    assert '## Constraints' not in result
    assert '## Examples' not in result
    assert '## Output Format' not in result


def test_prompt_render_template_substitution():
    p = Prompt(
        role='You are a {domain} expert.',
        guidelines=('Respond in {language}.',),
    )
    result = p.render(domain='weather', language='Korean')
    assert 'You are a weather expert.' in result
    assert 'Respond in Korean.' in result


def test_prompt_render_missing_variable_kept():
    p = Prompt(role='Hello {name}.')
    result = p.render()
    assert 'Hello {name}.' in result


def test_prompt_render_empty():
    p = Prompt()
    result = p.render()
    assert result == ''


def test_prompt_from_str():
    p = Prompt.from_str('You are helpful.')
    assert p.role == 'You are helpful.'
    assert isinstance(p, Prompt)


def test_prompt_render_multiple_examples():
    p = Prompt(
        examples=(
            Example(user='Q1', assistant='A1'),
            Example(user='Q2', assistant='A2'),
        ),
    )
    result = p.render()
    assert 'User: Q1' in result
    assert 'Assistant: A1' in result
    assert 'User: Q2' in result
    assert 'Assistant: A2' in result


def test_agent_accepts_str_instructions():
    client = MagicMock()
    agent = Agent(
        name='test',
        client=client,
        instructions='You are helpful.',
    )
    assert agent.instructions == 'You are helpful.'


def test_agent_accepts_prompt_instructions():
    client = MagicMock()
    prompt = Prompt(role='You are a bot.')
    agent = Agent(
        name='test',
        client=client,
        instructions=prompt,
    )
    assert isinstance(agent.instructions, Prompt)
    assert agent.instructions.render() == 'You are a bot.'
