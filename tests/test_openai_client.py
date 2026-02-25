"""
OpenAI API 클라이언트 테스트
- httpx MockTransport로 네트워크 호출 없이 검증
- 메시지/Tool 포맷 변환 검증
python -m pytest tests/test_openai_client.py -v
"""

import json

import httpx
import pytest

from sonya.core.llm.client.openai import OpenAIClient
from sonya.core.llm.errors import LLMAPIError
from sonya.core.llm.models import StopReason


def _make_mock_transport(response_body: dict, status_code: int = 200):
    """테스트용 httpx MockTransport 생성"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            json=response_body,
        )
    return httpx.MockTransport(handler)


MOCK_TEXT_RESPONSE = {
    "id": "chatcmpl-mock-1",
    "model": "gpt-4o",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "모의 응답입니다.",
        },
        "finish_reason": "stop",
    }],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}

MOCK_TOOL_CALL_RESPONSE = {
    "id": "chatcmpl-mock-2",
    "model": "gpt-4o",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_mock_1",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query": "테스트"}',
                    },
                },
            ],
        },
        "finish_reason": "tool_calls",
    }],
    "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
}

MOCK_MAX_TOKENS_RESPONSE = {
    "id": "chatcmpl-mock-3",
    "model": "gpt-4o",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "잘린 응답...",
        },
        "finish_reason": "length",
    }],
    "usage": {"prompt_tokens": 10, "completion_tokens": 4096, "total_tokens": 4106},
}


class TestOpenAIClient:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="api_key"):
            OpenAIClient()

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        client = OpenAIClient()
        assert client.api_key == "test-key-123"

    def test_provider_name(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        client = OpenAIClient()
        assert client.provider == "openai"

    @pytest.mark.asyncio
    async def test_chat_text_response(self):
        client = OpenAIClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_TEXT_RESPONSE))

        response = await client.chat(
            messages=[{"role": "user", "content": "안녕"}],
        )
        assert response.stop_reason == StopReason.END_TURN
        assert response.final_text() == "모의 응답입니다."
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_tool_call_response(self):
        client = OpenAIClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_TOOL_CALL_RESPONSE))

        response = await client.chat(
            messages=[{"role": "user", "content": "검색해줘"}],
            tools=[{"name": "web_search", "description": "검색", "input_schema": {}}],
        )
        assert response.stop_reason == StopReason.TOOL_USE
        tool_blocks = response.tool_use_blocks()
        assert len(tool_blocks) == 1
        assert tool_blocks[0].name == "web_search"
        assert tool_blocks[0].input == {"query": "테스트"}
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_max_tokens_response(self):
        client = OpenAIClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_MAX_TOKENS_RESPONSE))

        response = await client.chat(
            messages=[{"role": "user", "content": "긴 질문"}],
        )
        assert response.stop_reason == StopReason.MAX_TOKENS
        assert response.final_text() == "잘린 응답..."
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_sends_correct_body(self):
        """요청 body가 OpenAI 포맷으로 올바르게 변환되는지 검증"""
        captured_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(json.loads(request.content))
            return httpx.Response(200, json=MOCK_TEXT_RESPONSE)

        client = OpenAIClient(
            api_key="fake-key",
            model="gpt-4o-mini",
            max_tokens=1024,
            system="시스템 프롬프트",
        )
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        await client.chat(
            messages=[{"role": "user", "content": "테스트"}],
            tools=[{"name": "calc", "description": "계산기", "input_schema": {"type": "object"}}],
        )

        body = captured_requests[0]
        assert body["model"] == "gpt-4o-mini"
        assert body["max_tokens"] == 1024
        # system은 messages[0]에 삽입
        assert body["messages"][0] == {"role": "system", "content": "시스템 프롬프트"}
        assert body["messages"][1] == {"role": "user", "content": "테스트"}
        # tools는 OpenAI 포맷으로 변환
        assert body["tools"][0]["type"] == "function"
        assert body["tools"][0]["function"]["name"] == "calc"
        assert body["tools"][0]["function"]["parameters"] == {"type": "object"}
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_no_system_no_tools(self):
        """system과 tools가 없으면 body에 포함되지 않는지 검증"""
        captured_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(json.loads(request.content))
            return httpx.Response(200, json=MOCK_TEXT_RESPONSE)

        client = OpenAIClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        await client.chat(messages=[{"role": "user", "content": "안녕"}])

        body = captured_requests[0]
        # system 메시지 없음
        assert body["messages"] == [{"role": "user", "content": "안녕"}]
        assert "tools" not in body
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with OpenAIClient(api_key="fake-key") as client:
            client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_TEXT_RESPONSE))
            response = await client.chat(messages=[{"role": "user", "content": "hi"}])
            assert response.id == "chatcmpl-mock-1"

    @pytest.mark.asyncio
    async def test_http_error_raises_llm_api_error(self):
        """non-retryable HTTP 에러는 LLMAPIError로 래핑되어 즉시 전파"""
        error_response = {"error": {"message": "invalid key", "type": "invalid_request_error"}}
        client = OpenAIClient(api_key="bad-key")
        client._http = httpx.AsyncClient(
            transport=_make_mock_transport(error_response, status_code=401)
        )
        with pytest.raises(LLMAPIError) as exc_info:
            await client.chat(messages=[{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 401
        assert exc_info.value.provider == "openai"
        assert exc_info.value.retryable is False
        await client.close()


class TestMessageConversion:
    """Anthropic → OpenAI 메시지 포맷 변환 테스트"""

    def _client(self):
        return OpenAIClient(api_key="fake-key")

    def test_simple_text(self):
        client = self._client()
        result = client._convert_messages([
            {"role": "user", "content": "안녕"},
        ])
        assert result == [{"role": "user", "content": "안녕"}]

    def test_tool_result_conversion(self):
        """Anthropic tool_result → OpenAI tool role"""
        client = self._client()
        result = client._convert_messages([
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_1", "content": '{"result": 42}'},
                ],
            },
        ])
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "tu_1"
        assert result[0]["content"] == '{"result": 42}'

    def test_assistant_with_tool_use(self):
        """Anthropic assistant tool_use → OpenAI assistant tool_calls"""
        client = self._client()
        result = client._convert_messages([
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "검색하겠습니다."},
                    {"type": "tool_use", "id": "tu_1", "name": "search", "input": {"q": "날씨"}},
                ],
            },
        ])
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "검색하겠습니다."
        assert len(msg["tool_calls"]) == 1
        tc = msg["tool_calls"][0]
        assert tc["id"] == "tu_1"
        assert tc["function"]["name"] == "search"
        assert json.loads(tc["function"]["arguments"]) == {"q": "날씨"}


class TestToolConversion:
    """Anthropic → OpenAI Tool 스키마 변환 테스트"""

    def test_convert_tools(self):
        client = OpenAIClient(api_key="fake-key")
        anthropic_tools = [
            {
                "name": "calculator",
                "description": "수식 계산",
                "input_schema": {
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
            },
        ]
        result = client._convert_tools(anthropic_tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        fn = result[0]["function"]
        assert fn["name"] == "calculator"
        assert fn["description"] == "수식 계산"
        assert fn["parameters"]["properties"]["expression"]["type"] == "string"


class TestProviderSchema:
    """BaseTool.to_llm_schema(provider=...) 테스트"""

    def test_anthropic_format_default(self):
        from sonya.core.tools.examples.web_search import WebSearchTool
        schema = WebSearchTool().to_llm_schema()
        assert "input_schema" in schema
        assert "name" in schema
        assert "type" not in schema

    def test_anthropic_format_explicit(self):
        from sonya.core.tools.examples.web_search import WebSearchTool
        schema = WebSearchTool().to_llm_schema(provider="anthropic")
        assert "input_schema" in schema

    def test_openai_format(self):
        from sonya.core.tools.examples.web_search import WebSearchTool
        schema = WebSearchTool().to_llm_schema(provider="openai")
        assert schema["type"] == "function"
        assert "function" in schema
        fn = schema["function"]
        assert fn["name"] == "web_search"
        assert "parameters" in fn
        assert "query" in fn["parameters"]["properties"]

    def test_registry_schemas_with_provider(self):
        from sonya.core.tools.examples.web_search import WebSearchTool
        from sonya.core.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(WebSearchTool())

        anthropic_schemas = registry.schemas(provider="anthropic")
        assert "input_schema" in anthropic_schemas[0]

        openai_schemas = registry.schemas(provider="openai")
        assert openai_schemas[0]["type"] == "function"
