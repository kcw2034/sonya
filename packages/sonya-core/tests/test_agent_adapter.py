"""Tests for agent._adapter — mock response parsing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sonya.core.parsers.adapter import (
    AnthropicAdapter,
    GeminiAdapter,
    OpenAIAdapter,
)


# ---- Anthropic Adapter Tests ----

class TestAnthropicAdapter:
    def _make_response(
        self,
        content: list[Any],
        stop_reason: str = 'end_turn',
    ) -> SimpleNamespace:
        return SimpleNamespace(content=content, stop_reason=stop_reason)

    def test_parse_text_only(self) -> None:
        adapter = AnthropicAdapter()
        response = self._make_response([
            SimpleNamespace(type='text', text='Hello world'),
        ])
        parsed = adapter.parse(response)
        assert parsed.text == 'Hello world'
        assert parsed.tool_calls == []
        assert parsed.stop_reason == 'end'

    def test_parse_tool_use(self) -> None:
        adapter = AnthropicAdapter()
        response = self._make_response(
            [
                SimpleNamespace(type='text', text='Let me search'),
                SimpleNamespace(
                    type='tool_use',
                    id='tc_123',
                    name='search',
                    input={'query': 'hello'},
                ),
            ],
            stop_reason='tool_use',
        )
        parsed = adapter.parse(response)
        assert parsed.text == 'Let me search'
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == 'search'
        assert parsed.tool_calls[0].arguments == {'query': 'hello'}
        assert parsed.stop_reason == 'tool_use'

    def test_format_assistant_message(self) -> None:
        adapter = AnthropicAdapter()
        response = self._make_response([
            SimpleNamespace(type='text', text='Hi'),
        ])
        msg = adapter.format_assistant_message(response)
        assert msg['role'] == 'assistant'
        assert msg['content'][0]['type'] == 'text'

    def test_format_tool_results_message(self) -> None:
        adapter = AnthropicAdapter()
        results = [
            {'call_id': 'tc_1', 'success': True, 'output': 'done'},
        ]
        msg = adapter.format_tool_results_message(results)
        assert msg['role'] == 'user'
        assert msg['content'][0]['type'] == 'tool_result'
        assert msg['content'][0]['tool_use_id'] == 'tc_1'

    def test_format_generate_kwargs(self) -> None:
        adapter = AnthropicAdapter()
        result = adapter.format_generate_kwargs(
            'You are helpful', [{'name': 'test'}]
        )
        assert result['system'] == 'You are helpful'
        assert result['tools'] == [{'name': 'test'}]

    def test_format_generate_kwargs_no_tools(self) -> None:
        adapter = AnthropicAdapter()
        result = adapter.format_generate_kwargs('Hello', None)
        assert result == {'system': 'Hello'}


# ---- OpenAI Adapter Tests ----

class TestOpenAIAdapter:
    def _make_response(
        self,
        content: str | None = None,
        tool_calls: list[Any] | None = None,
        finish_reason: str = 'stop',
    ) -> SimpleNamespace:
        message = SimpleNamespace(
            content=content,
            tool_calls=tool_calls,
        )
        choice = SimpleNamespace(
            message=message,
            finish_reason=finish_reason,
        )
        return SimpleNamespace(choices=[choice])

    def test_parse_text_only(self) -> None:
        adapter = OpenAIAdapter()
        response = self._make_response(content='Hello')
        parsed = adapter.parse(response)
        assert parsed.text == 'Hello'
        assert parsed.tool_calls == []
        assert parsed.stop_reason == 'end'

    def test_parse_tool_calls(self) -> None:
        adapter = OpenAIAdapter()
        tc = SimpleNamespace(
            id='call_abc',
            function=SimpleNamespace(
                name='search',
                arguments='{"query": "test"}',
            ),
        )
        response = self._make_response(
            content='Searching...',
            tool_calls=[tc],
            finish_reason='tool_calls',
        )
        parsed = adapter.parse(response)
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == 'search'
        assert parsed.tool_calls[0].arguments == {'query': 'test'}
        assert parsed.stop_reason == 'tool_use'

    def test_format_assistant_message(self) -> None:
        adapter = OpenAIAdapter()
        response = self._make_response(content='Hi')
        msg = adapter.format_assistant_message(response)
        assert msg['role'] == 'assistant'
        assert msg['content'] == 'Hi'

    def test_format_tool_results_message(self) -> None:
        adapter = OpenAIAdapter()
        results = [
            {'call_id': 'call_1', 'success': True, 'output': 'ok'},
        ]
        msgs = adapter.format_tool_results_message(results)
        assert isinstance(msgs, list)
        assert msgs[0]['role'] == 'tool'
        assert msgs[0]['tool_call_id'] == 'call_1'


# ---- Gemini Adapter Tests ----

class TestGeminiAdapter:
    def _make_response(
        self,
        parts: list[Any] | None = None,
    ) -> SimpleNamespace:
        content = SimpleNamespace(parts=parts or [])
        candidate = SimpleNamespace(content=content)
        return SimpleNamespace(candidates=[candidate])

    def test_parse_text_only(self) -> None:
        adapter = GeminiAdapter()
        response = self._make_response([
            SimpleNamespace(text='Hello', function_call=None),
        ])
        parsed = adapter.parse(response)
        assert parsed.text == 'Hello'
        assert parsed.tool_calls == []
        assert parsed.stop_reason == 'end'

    def test_parse_function_call(self) -> None:
        adapter = GeminiAdapter()
        fc = SimpleNamespace(name='search', args={'q': 'test'})
        response = self._make_response([
            SimpleNamespace(text=None, function_call=fc),
        ])
        parsed = adapter.parse(response)
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == 'search'
        assert parsed.tool_calls[0].arguments == {'q': 'test'}
        assert parsed.stop_reason == 'tool_use'

    def test_format_assistant_message(self) -> None:
        adapter = GeminiAdapter()
        response = self._make_response([
            SimpleNamespace(text='Hi', function_call=None),
        ])
        msg = adapter.format_assistant_message(response)
        assert msg['role'] == 'model'
        assert msg['parts'][0]['text'] == 'Hi'

    def test_format_tool_results_message(self) -> None:
        adapter = GeminiAdapter()
        results = [
            {'name': 'search', 'success': True, 'output': 'found'},
        ]
        msg = adapter.format_tool_results_message(results)
        assert msg['role'] == 'user'
        assert 'function_response' in msg['parts'][0]


# ---- GeminiAdapter.format_messages Tests ----

class TestGeminiFormatMessages:
    """Tests for GeminiAdapter.format_messages."""

    def test_openai_format_user_message(self) -> None:
        adapter = GeminiAdapter()
        msgs = [{'role': 'user', 'content': 'Hello'}]
        result = adapter.format_messages(msgs)
        assert result == [
            {'role': 'user', 'parts': [{'text': 'Hello'}]}
        ]

    def test_openai_format_assistant_message(self) -> None:
        adapter = GeminiAdapter()
        msgs = [{'role': 'assistant', 'content': 'Hi'}]
        result = adapter.format_messages(msgs)
        assert result == [
            {'role': 'model', 'parts': [{'text': 'Hi'}]}
        ]

    def test_system_role_mapped_to_user(self) -> None:
        adapter = GeminiAdapter()
        msgs = [{'role': 'system', 'content': 'Be helpful'}]
        result = adapter.format_messages(msgs)
        assert result[0]['role'] == 'user'

    def test_gemini_format_passthrough(self) -> None:
        adapter = GeminiAdapter()
        msgs = [
            {'role': 'model', 'parts': [{'text': 'Hi'}]}
        ]
        result = adapter.format_messages(msgs)
        assert result == msgs

    def test_mixed_formats(self) -> None:
        adapter = GeminiAdapter()
        msgs = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'model', 'parts': [{'text': 'Hi'}]},
            {'role': 'user', 'parts': [
                {'function_response': {
                    'name': 'f', 'response': {},
                }}
            ]},
        ]
        result = adapter.format_messages(msgs)
        assert result[0] == {
            'role': 'user', 'parts': [{'text': 'Hello'}]
        }
        assert result[1] == msgs[1]
        assert result[2] == msgs[2]

    def test_empty_content(self) -> None:
        adapter = GeminiAdapter()
        msgs = [{'role': 'user', 'content': ''}]
        result = adapter.format_messages(msgs)
        assert result == [{'role': 'user', 'parts': []}]


# ---- Passthrough format_messages Tests ----

class TestPassthroughFormatMessages:
    """Anthropic/OpenAI adapters pass messages through."""

    def test_anthropic_passthrough(self) -> None:
        adapter = AnthropicAdapter()
        msgs = [{'role': 'user', 'content': 'Hi'}]
        assert adapter.format_messages(msgs) is msgs

    def test_openai_passthrough(self) -> None:
        adapter = OpenAIAdapter()
        msgs = [{'role': 'user', 'content': 'Hi'}]
        assert adapter.format_messages(msgs) is msgs
