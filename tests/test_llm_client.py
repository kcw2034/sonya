"""
Anthropic API 클라이언트 테스트
- httpx MockTransport로 네트워크 호출 없이 검증
python -m pytest tests/test_llm_client.py -v
"""

import json

import httpx
import pytest

from sonya_core.llm.client import AnthropicClient, ANTHROPIC_API_URL
from sonya_core.llm.models import StopReason


def _make_mock_transport(response_body: dict, status_code: int = 200):
    """테스트용 httpx MockTransport 생성"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            json=response_body,
        )
    return httpx.MockTransport(handler)


MOCK_TEXT_RESPONSE = {
    "id": "msg_mock_1",
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "end_turn",
    "content": [{"type": "text", "text": "모의 응답입니다."}],
    "usage": {"input_tokens": 10, "output_tokens": 5},
}

MOCK_TOOL_USE_RESPONSE = {
    "id": "msg_mock_2",
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "tool_use",
    "content": [
        {"type": "text", "text": "검색하겠습니다."},
        {
            "type": "tool_use",
            "id": "tu_mock_1",
            "name": "web_search",
            "input": {"query": "테스트"},
        },
    ],
    "usage": {"input_tokens": 20, "output_tokens": 15},
}


class TestAnthropicClient:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="api_key"):
            AnthropicClient()

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
        client = AnthropicClient()
        assert client.api_key == "test-key-123"

    @pytest.mark.asyncio
    async def test_chat_text_response(self):
        client = AnthropicClient(api_key="fake-key")
        # mock transport 주입
        client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_TEXT_RESPONSE))

        response = await client.chat(
            messages=[{"role": "user", "content": "안녕"}],
        )
        assert response.stop_reason == StopReason.END_TURN
        assert response.final_text() == "모의 응답입니다."
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_tool_use_response(self):
        client = AnthropicClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_TOOL_USE_RESPONSE))

        response = await client.chat(
            messages=[{"role": "user", "content": "검색해줘"}],
            tools=[{"name": "web_search", "description": "검색", "input_schema": {}}],
        )
        assert response.stop_reason == StopReason.TOOL_USE
        assert len(response.tool_use_blocks()) == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_sends_correct_body(self):
        """요청 body가 올바르게 구성되는지 검증"""
        captured_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(json.loads(request.content))
            return httpx.Response(200, json=MOCK_TEXT_RESPONSE)

        client = AnthropicClient(
            api_key="fake-key",
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="시스템 프롬프트",
        )
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        await client.chat(
            messages=[{"role": "user", "content": "테스트"}],
            tools=[{"name": "calc", "description": "계산기", "input_schema": {}}],
        )

        body = captured_requests[0]
        assert body["model"] == "claude-haiku-4-5-20251001"
        assert body["max_tokens"] == 1024
        assert body["system"] == "시스템 프롬프트"
        assert body["tools"] == [{"name": "calc", "description": "계산기", "input_schema": {}}]
        assert body["messages"] == [{"role": "user", "content": "테스트"}]
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_no_system_no_tools(self):
        """system과 tools가 없으면 body에 포함되지 않는지 검증"""
        captured_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(json.loads(request.content))
            return httpx.Response(200, json=MOCK_TEXT_RESPONSE)

        client = AnthropicClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        await client.chat(messages=[{"role": "user", "content": "안녕"}])

        body = captured_requests[0]
        assert "system" not in body
        assert "tools" not in body
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with AnthropicClient(api_key="fake-key") as client:
            client._http = httpx.AsyncClient(transport=_make_mock_transport(MOCK_TEXT_RESPONSE))
            response = await client.chat(messages=[{"role": "user", "content": "hi"}])
            assert response.id == "msg_mock_1"

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        error_response = {"type": "error", "error": {"type": "authentication_error", "message": "invalid key"}}
        client = AnthropicClient(api_key="bad-key")
        client._http = httpx.AsyncClient(
            transport=_make_mock_transport(error_response, status_code=401)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat(messages=[{"role": "user", "content": "hi"}])
        await client.close()
