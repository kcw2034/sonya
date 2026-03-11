# Prompt Builder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** sonya-core에 구조화된 프롬프트 빌더(Prompt, Example)를 추가하고, OpenAI 시스템 메시지 버그를 수정한다.

**Architecture:** Prompt frozen dataclass를 models/prompt.py에 추가. Agent.instructions 타입을 `str | Prompt`로 변경. AgentRuntime에서 Prompt 객체를 render()하여 문자열로 변환 후 어댑터에 전달. OpenAI 어댑터의 format_generate_kwargs()를 수정하여 instructions를 system message로 처리.

**Tech Stack:** Python 3.11+, dataclasses, pytest

**Design doc:** `docs/plans/2026-03-11-prompt-builder-design.md`

---

### Task 1: Example 데이터클래스

**Files:**
- Create: `packages/sonya-core/src/sonya/core/models/prompt.py`
- Test: `packages/sonya-core/tests/test_prompt.py`

**Step 1: Write the failing test**

```python
# tests/test_prompt.py
"""Tests for Prompt and Example data types."""

from sonya.core.models.prompt import Example


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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write minimal implementation**

```python
# models/prompt.py
"""Structured prompt types for agent instructions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Example:
    """Few-shot example pair.

    Args:
        user: User message content.
        assistant: Expected assistant response.
    """

    user: str
    assistant: str
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/prompt.py packages/sonya-core/tests/test_prompt.py
git commit -m "feat(sonya-core): add Example dataclass for few-shot prompts"
```

---

### Task 2: Prompt 데이터클래스 + render()

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/models/prompt.py`
- Test: `packages/sonya-core/tests/test_prompt.py`

**Step 1: Write the failing test**

Append to `tests/test_prompt.py`:

```python
from sonya.core.models.prompt import Example, Prompt


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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt.py -v`
Expected: FAIL with `ImportError: cannot import name 'Prompt'`

**Step 3: Write minimal implementation**

Add to `packages/sonya-core/src/sonya/core/models/prompt.py` after Example:

```python
from collections import defaultdict


@dataclass(frozen=True, slots=True)
class Prompt:
    """Structured prompt with named sections.

    Sections are rendered in order: role, guidelines,
    constraints, examples, output_format. Empty sections
    are skipped. Template variables use ``{placeholder}``
    syntax, substituted via ``render(**context)``.

    Args:
        role: Agent identity and expertise scope.
        guidelines: Behavioral rules (do this).
        constraints: Restrictions (don't do this).
        examples: Few-shot example pairs.
        output_format: Expected response structure.

    Example::

        prompt = Prompt(
            role='You are a {domain} expert.',
            guidelines=('Use tools first.',),
            constraints=('Never fabricate data.',),
            examples=(
                Example(user='Hello', assistant='Hi!'),
            ),
            output_format='Respond in JSON.',
        )
        text = prompt.render(domain='weather')
    """

    role: str = ''
    guidelines: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    examples: tuple[Example, ...] = ()
    output_format: str = ''

    def render(self, **context: str) -> str:
        """Render prompt to final string.

        Assembles non-empty sections in order and
        substitutes ``{placeholder}`` variables from
        *context*. Missing variables are left as-is.

        Args:
            **context: Template variable substitutions.

        Returns:
            Rendered prompt string.
        """
        sections: list[str] = []

        if self.role:
            sections.append(self.role)

        if self.guidelines:
            lines = '\n'.join(
                f'- {g}' for g in self.guidelines
            )
            sections.append(f'## Guidelines\n{lines}')

        if self.constraints:
            lines = '\n'.join(
                f'- {c}' for c in self.constraints
            )
            sections.append(f'## Constraints\n{lines}')

        if self.examples:
            parts: list[str] = []
            for ex in self.examples:
                parts.append(
                    f'User: {ex.user}\n'
                    f'Assistant: {ex.assistant}'
                )
            body = '\n\n'.join(parts)
            sections.append(f'## Examples\n\n{body}')

        if self.output_format:
            sections.append(
                f'## Output Format\n{self.output_format}'
            )

        text = '\n\n'.join(sections)

        if context:
            safe = defaultdict(str, context)
            text = text.format_map(safe)

        return text

    @staticmethod
    def from_str(text: str) -> 'Prompt':
        """Create a Prompt with the given text as role.

        Args:
            text: Plain text to use as the role section.

        Returns:
            A new Prompt instance.
        """
        return Prompt(role=text)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt.py -v`
Expected: 13 passed (3 Example + 10 Prompt)

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/prompt.py packages/sonya-core/tests/test_prompt.py
git commit -m "feat(sonya-core): add Prompt dataclass with render() and from_str()"
```

---

### Task 3: Agent.instructions 타입 변경

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/models/agent.py:1-36`
- Test: `packages/sonya-core/tests/test_prompt.py`

**Step 1: Write the failing test**

Append to `tests/test_prompt.py`:

```python
from unittest.mock import MagicMock
from sonya.core.models.agent import Agent


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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt.py::test_agent_accepts_prompt_instructions -v`
Expected: FAIL (type error or unexpected behavior since instructions is typed as str)

**Step 3: Write minimal implementation**

Modify `packages/sonya-core/src/sonya/core/models/agent.py`:

```python
"""Agent and AgentResult data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sonya.core.client.provider.base import BaseClient
from sonya.core.models.prompt import Prompt
from sonya.core.models.tool import Tool
from sonya.core.schemas.types import AgentCallback


@dataclass(slots=True)
class Agent:
    """Describes an autonomous agent that can use tools and hand off.

    Args:
        name: Unique agent identifier.
        client: LLM client to use for generation.
        instructions: System prompt — plain string or
            structured :class:`Prompt` object.
        tools: List of tools available to the agent.
        handoffs: List of agents this agent can hand off to.
        max_iterations: Maximum LLM <-> tool loop iterations.
        callbacks: Agent lifecycle callbacks.
    """

    name: str
    client: BaseClient
    instructions: str | Prompt = ''
    tools: list[Tool] = field(default_factory=list)
    handoffs: list[Agent] = field(default_factory=list)
    max_iterations: int = 10
    callbacks: list[AgentCallback] = field(
        default_factory=list
    )
```

Note: `AgentResult` remains unchanged below.

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt.py -v`
Expected: 15 passed

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/agent.py packages/sonya-core/tests/test_prompt.py
git commit -m "feat(sonya-core): accept str | Prompt for Agent.instructions"
```

---

### Task 4: AgentRuntime Prompt 통합 + prompt_context 지원

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/models/agent_runtime.py:56-93`
- Test: `packages/sonya-core/tests/test_prompt_runtime.py`

**Step 1: Write the failing test**

```python
# tests/test_prompt_runtime.py
"""Tests for AgentRuntime Prompt integration."""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from sonya.core.models.agent import Agent, AgentResult
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.models.prompt import Prompt, Example
from sonya.core.client.provider.base import BaseClient


class _DummyClient(BaseClient):
    """Client that returns a canned text response."""

    def __init__(self, text: str = 'hello') -> None:
        super().__init__(
            config=MagicMock(model='test'),
            interceptors=[],
        )
        self._text = text

    async def _provider_generate(self, messages, **kwargs):
        return SimpleNamespace(
            content=[
                SimpleNamespace(type='text', text=self._text)
            ],
            stop_reason='end_turn',
        )

    async def _provider_generate_stream(
        self, messages, **kwargs
    ):
        yield self._provider_generate(messages, **kwargs)


@pytest.mark.asyncio
async def test_runtime_with_str_instructions():
    agent = Agent(
        name='test',
        client=_DummyClient(),
        instructions='Be helpful.',
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'hello'


@pytest.mark.asyncio
async def test_runtime_with_prompt_instructions():
    agent = Agent(
        name='test',
        client=_DummyClient(),
        instructions=Prompt(
            role='You are a bot.',
            guidelines=('Be concise.',),
        ),
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert result.text == 'hello'


@pytest.mark.asyncio
async def test_runtime_with_prompt_context():
    agent = Agent(
        name='test',
        client=_DummyClient(),
        instructions=Prompt(
            role='You are a {domain} expert.',
        ),
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}],
        prompt_context={'domain': 'weather'},
    )
    assert result.text == 'hello'


@pytest.mark.asyncio
async def test_runtime_prompt_context_ignored_for_str():
    agent = Agent(
        name='test',
        client=_DummyClient(),
        instructions='Static prompt.',
    )
    runtime = AgentRuntime(agent)
    result = await runtime.run(
        [{'role': 'user', 'content': 'hi'}],
        prompt_context={'domain': 'weather'},
    )
    assert result.text == 'hello'
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_runtime.py -v`
Expected: FAIL (prompt_context parameter doesn't exist)

**Step 3: Write minimal implementation**

Modify `packages/sonya-core/src/sonya/core/models/agent_runtime.py`. Change the `run` method signature and add Prompt resolution:

Change lines 56-93 to:

```python
    async def run(
        self,
        messages: list[dict[str, Any]],
        prompt_context: dict[str, str] | None = None,
    ) -> AgentResult:
        """Execute the agent loop starting from *messages*.

        Args:
            messages: Initial conversation messages.
            prompt_context: Optional template variables for
                :class:`Prompt` rendering.

        Returns:
            :class:`AgentResult` with the final text and history.

        Raises:
            AgentError: If the loop exceeds max_iterations.
        """
        from sonya.core.models.prompt import Prompt

        agent = self._agent
        adapter = self._adapter
        registry = self._registry
        history = list(messages)

        # Resolve instructions
        instructions = agent.instructions
        if isinstance(instructions, Prompt):
            instructions = instructions.render(
                **(prompt_context or {})
            )

        # Build generate kwargs via adapter
        tools = registry.tools
        schemas: list[dict[str, Any]] | None = None
        if tools:
            provider_name = type(agent.client).__name__
            _provider_map = {
                'AnthropicClient': 'anthropic',
                'OpenAIClient': 'openai',
                'GeminiClient': 'gemini',
            }
            provider = _provider_map.get(
                provider_name, 'openai'
            )
            schemas = registry.schemas(provider)

        gen_kwargs = adapter.format_generate_kwargs(
            instructions, schemas
        )
```

Everything after line 93 (the for loop) remains unchanged.

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_runtime.py -v`
Expected: 4 passed

**Step 5: Verify no regressions**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/ -v`
Expected: All existing tests pass

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/agent_runtime.py packages/sonya-core/tests/test_prompt_runtime.py
git commit -m "feat(sonya-core): integrate Prompt with AgentRuntime + prompt_context"
```

---

### Task 5: OpenAI 시스템 메시지 버그 수정

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/parsers/adapter.py:231-244`
- Test: `packages/sonya-core/tests/test_prompt_openai_fix.py`

**Step 1: Write the failing test**

```python
# tests/test_prompt_openai_fix.py
"""Tests for OpenAI system message injection fix."""

from sonya.core.parsers.adapter import OpenAIAdapter


def test_openai_format_generate_kwargs_includes_system():
    adapter = OpenAIAdapter()
    kwargs = adapter.format_generate_kwargs(
        'You are helpful.', None
    )
    assert '_system_message' in kwargs
    assert kwargs['_system_message'] == 'You are helpful.'


def test_openai_format_generate_kwargs_no_instructions():
    adapter = OpenAIAdapter()
    kwargs = adapter.format_generate_kwargs('', None)
    assert '_system_message' not in kwargs


def test_openai_format_generate_kwargs_with_tools():
    adapter = OpenAIAdapter()
    tools = [{'type': 'function', 'function': {'name': 'f'}}]
    kwargs = adapter.format_generate_kwargs(
        'Be helpful.', tools
    )
    assert kwargs['_system_message'] == 'Be helpful.'
    assert kwargs['tools'] == tools
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_openai_fix.py -v`
Expected: FAIL (no `_system_message` key in kwargs)

**Step 3: Write minimal implementation**

Modify `packages/sonya-core/src/sonya/core/parsers/adapter.py` lines 231-244:

```python
    def format_generate_kwargs(
        self,
        instructions: str,
        tool_schemas: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build OpenAI-specific generate kwargs.

        Stores instructions under ``_system_message`` for the
        runtime to prepend as a system message.
        """
        kwargs: dict[str, Any] = {}
        if instructions:
            kwargs['_system_message'] = instructions
        if tool_schemas:
            kwargs['tools'] = tool_schemas
        return kwargs
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_openai_fix.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add packages/sonya-core/src/sonya/core/parsers/adapter.py packages/sonya-core/tests/test_prompt_openai_fix.py
git commit -m "fix(sonya-core): store OpenAI instructions as _system_message"
```

---

### Task 6: AgentRuntime에서 _system_message 처리

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/models/agent_runtime.py:91-107`
- Test: `packages/sonya-core/tests/test_prompt_openai_fix.py`

**Step 1: Write the failing test**

Append to `tests/test_prompt_openai_fix.py`:

```python
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from sonya.core.models.agent import Agent
from sonya.core.models.agent_runtime import AgentRuntime
from sonya.core.client.provider.base import BaseClient


class _DummyOpenAIClient(BaseClient):
    """Fake OpenAI client that captures messages."""

    def __init__(self) -> None:
        super().__init__(
            config=MagicMock(model='test'),
            interceptors=[],
        )
        self.captured_messages = None

    async def _provider_generate(self, messages, **kwargs):
        self.captured_messages = messages
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='ok',
                        tool_calls=None,
                    ),
                    finish_reason='stop',
                )
            ]
        )

    async def _provider_generate_stream(
        self, messages, **kwargs
    ):
        yield await self._provider_generate(
            messages, **kwargs
        )


# Patch class name so adapter detection works
_DummyOpenAIClient.__name__ = 'OpenAIClient'


@pytest.mark.asyncio
async def test_runtime_prepends_system_message_for_openai():
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='You are helpful.',
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'system'
    assert msgs[0]['content'] == 'You are helpful.'
    assert msgs[1]['role'] == 'user'


@pytest.mark.asyncio
async def test_runtime_no_system_message_when_empty():
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='',
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'user'
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_openai_fix.py::test_runtime_prepends_system_message_for_openai -v`
Expected: FAIL (system message not prepended)

**Step 3: Write minimal implementation**

Modify `packages/sonya-core/src/sonya/core/models/agent_runtime.py`. After the `gen_kwargs = adapter.format_generate_kwargs(...)` line, add system message extraction:

Replace the block around lines 91-107 (after instructions resolution, before the for loop):

```python
        gen_kwargs = adapter.format_generate_kwargs(
            instructions, schemas
        )

        # Extract system message for OpenAI-style injection
        system_message = gen_kwargs.pop(
            '_system_message', None
        )
        if system_message:
            history = [
                {'role': 'system', 'content': system_message}
            ] + history

        for _iteration in range(agent.max_iterations):
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_openai_fix.py -v`
Expected: 5 passed

**Step 5: Verify no regressions**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/models/agent_runtime.py packages/sonya-core/tests/test_prompt_openai_fix.py
git commit -m "fix(sonya-core): prepend system message for OpenAI in AgentRuntime"
```

---

### Task 7: 패키지 exports 업데이트

**Files:**
- Modify: `packages/sonya-core/src/sonya/core/__init__.py`
- Test: `packages/sonya-core/tests/test_imports.py`

**Step 1: Write the failing test**

Append to existing `tests/test_imports.py` (or create if needed):

```python
def test_prompt_exports():
    from sonya.core import Prompt, Example
    assert Prompt is not None
    assert Example is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_imports.py::test_prompt_exports -v`
Expected: FAIL with `ImportError`

**Step 3: Write minimal implementation**

Add to `packages/sonya-core/src/sonya/core/__init__.py`:

After the agent import line (`from sonya.core.models.agent import Agent, AgentResult`), add:

```python
from sonya.core.models.prompt import Example, Prompt
```

Add to `__all__` list after the Agent section:

```python
    # Prompt
    "Example",
    "Prompt",
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_imports.py -v`
Expected: All tests pass

**Step 5: Run full test suite**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add packages/sonya-core/src/sonya/core/__init__.py packages/sonya-core/tests/test_imports.py
git commit -m "feat(sonya-core): export Prompt and Example from package"
```

---

### Task 8: 통합 테스트

**Files:**
- Test: `packages/sonya-core/tests/test_prompt_integration.py`

**Step 1: Write the integration test**

```python
# tests/test_prompt_integration.py
"""Integration tests for the Prompt system."""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from sonya.core import Agent, AgentRuntime, Prompt, Example
from sonya.core.client.provider.base import BaseClient


class _DummyAnthropicClient(BaseClient):
    """Fake Anthropic client that captures kwargs."""

    def __init__(self) -> None:
        super().__init__(
            config=MagicMock(model='test'),
            interceptors=[],
        )
        self.captured_kwargs = None

    async def _provider_generate(self, messages, **kwargs):
        self.captured_kwargs = kwargs
        return SimpleNamespace(
            content=[
                SimpleNamespace(type='text', text='ok')
            ],
            stop_reason='end_turn',
        )

    async def _provider_generate_stream(
        self, messages, **kwargs
    ):
        yield await self._provider_generate(
            messages, **kwargs
        )


_DummyAnthropicClient.__name__ = 'AnthropicClient'


class _DummyOpenAIClient(BaseClient):
    """Fake OpenAI client that captures messages."""

    def __init__(self) -> None:
        super().__init__(
            config=MagicMock(model='test'),
            interceptors=[],
        )
        self.captured_messages = None

    async def _provider_generate(self, messages, **kwargs):
        self.captured_messages = messages
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='ok',
                        tool_calls=None,
                    ),
                    finish_reason='stop',
                )
            ]
        )

    async def _provider_generate_stream(
        self, messages, **kwargs
    ):
        yield await self._provider_generate(
            messages, **kwargs
        )


_DummyOpenAIClient.__name__ = 'OpenAIClient'


@pytest.mark.asyncio
async def test_structured_prompt_with_anthropic():
    """Prompt renders and passes to Anthropic as system."""
    client = _DummyAnthropicClient()
    agent = Agent(
        name='test',
        client=client,
        instructions=Prompt(
            role='You are a weather bot.',
            guidelines=('Be concise.',),
            constraints=('No fabrication.',),
            examples=(
                Example(
                    user='Weather in Seoul?',
                    assistant='Checking...',
                ),
            ),
        ),
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    system = client.captured_kwargs.get('system', '')
    assert 'You are a weather bot.' in system
    assert '## Guidelines' in system
    assert '- Be concise.' in system
    assert '## Constraints' in system
    assert 'User: Weather in Seoul?' in system


@pytest.mark.asyncio
async def test_dynamic_prompt_with_openai():
    """Dynamic Prompt renders with context for OpenAI."""
    client = _DummyOpenAIClient()
    agent = Agent(
        name='test',
        client=client,
        instructions=Prompt(
            role='You are a {domain} expert.',
        ),
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}],
        prompt_context={'domain': 'cooking'},
    )
    msgs = client.captured_messages
    assert msgs[0]['role'] == 'system'
    assert 'cooking expert' in msgs[0]['content']


@pytest.mark.asyncio
async def test_backward_compat_str_instructions():
    """Plain string instructions still work."""
    client = _DummyAnthropicClient()
    agent = Agent(
        name='test',
        client=client,
        instructions='Be helpful.',
    )
    runtime = AgentRuntime(agent)
    await runtime.run(
        [{'role': 'user', 'content': 'hi'}]
    )
    assert client.captured_kwargs['system'] == 'Be helpful.'
```

**Step 2: Run the integration test**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/test_prompt_integration.py -v`
Expected: 3 passed

**Step 3: Run full test suite**

Run: `cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya/packages/sonya-core && python -m pytest tests/ -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add packages/sonya-core/tests/test_prompt_integration.py
git commit -m "test(sonya-core): add prompt system integration tests"
```
