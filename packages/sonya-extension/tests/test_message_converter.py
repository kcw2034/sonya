"""Tests for message format converters."""

from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from sonya.extension.schemas.types import (
    langchain_to_sonya_messages,
    sonya_to_langchain_messages,
)


class TestSonyaToLangchain:
    """Tests for sonya → LangChain message conversion."""

    def test_basic_messages(self) -> None:
        """System, user, assistant messages convert."""
        sonya_msgs = [
            {'role': 'system', 'content': 'You are helpful.'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there!'},
        ]

        result = sonya_to_langchain_messages(sonya_msgs)

        assert len(result) == 3
        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)
        assert result[0].content == 'You are helpful.'
        assert result[1].content == 'Hello'
        assert result[2].content == 'Hi there!'

    def test_tool_call_message(self) -> None:
        """Assistant message with tool calls converts."""
        sonya_msgs = [
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'call_1',
                    'type': 'function',
                    'function': {
                        'name': 'get_weather',
                        'arguments': {'city': 'Seoul'},
                    },
                }],
            },
        ]

        result = sonya_to_langchain_messages(sonya_msgs)

        assert len(result) == 1
        ai_msg = result[0]
        assert isinstance(ai_msg, AIMessage)
        assert len(ai_msg.tool_calls) == 1
        assert ai_msg.tool_calls[0]['name'] == 'get_weather'

    def test_tool_result_message(self) -> None:
        """Tool result message converts."""
        sonya_msgs = [
            {
                'role': 'tool',
                'tool_call_id': 'call_1',
                'content': 'Sunny, 25C',
            },
        ]

        result = sonya_to_langchain_messages(sonya_msgs)

        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content == 'Sunny, 25C'
        assert result[0].tool_call_id == 'call_1'


class TestLangchainToSonya:
    """Tests for LangChain → sonya message conversion."""

    def test_basic_messages(self) -> None:
        """LangChain messages convert to sonya dicts."""
        lc_msgs = [
            SystemMessage(content='Be helpful.'),
            HumanMessage(content='Hi'),
            AIMessage(content='Hello!'),
        ]

        result = langchain_to_sonya_messages(lc_msgs)

        assert len(result) == 3
        assert result[0] == {
            'role': 'system', 'content': 'Be helpful.',
        }
        assert result[1] == {
            'role': 'user', 'content': 'Hi',
        }
        assert result[2] == {
            'role': 'assistant', 'content': 'Hello!',
        }

    def test_tool_call_roundtrip(self) -> None:
        """Tool call messages survive roundtrip conversion."""
        original = [
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'call_x',
                    'type': 'function',
                    'function': {
                        'name': 'search',
                        'arguments': {'q': 'test'},
                    },
                }],
            },
        ]

        lc = sonya_to_langchain_messages(original)
        back = langchain_to_sonya_messages(lc)

        assert len(back) == 1
        assert back[0]['role'] == 'assistant'
        assert len(back[0]['tool_calls']) == 1
        tc = back[0]['tool_calls'][0]
        assert tc['function']['name'] == 'search'
