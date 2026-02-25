"""
Anthropic API 클라이언트 테스트
- httpx MockTransport로 네트워크 호출 없이 검증
- 재시도 로직 검증
python -m pytest tests/test_llm_client.py -v
"""

import json

import httpx
import pytest

from sonya.core.llm.client import AnthropicClient
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

MOCK_STREAM_RESPONSE = "\n".join(
    [
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_stream_1","model":"claude-sonnet-4-20250514","usage":{"input_tokens":11}}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"안"}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"녕"}}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    ]
)


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
        client._http = httpx.AsyncClient(
            transport=_make_mock_transport(MOCK_TEXT_RESPONSE)
        )

        response = await client.chat(
            messages=[{"role": "user", "content": "안녕"}],
        )
        assert response.stop_reason == StopReason.END_TURN
        assert response.final_text() == "모의 응답입니다."
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_tool_use_response(self):
        client = AnthropicClient(api_key="fake-key")
        client._http = httpx.AsyncClient(
            transport=_make_mock_transport(MOCK_TOOL_USE_RESPONSE)
        )

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
        assert body["tools"] == [
            {"name": "calc", "description": "계산기", "input_schema": {}}
        ]
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
            client._http = httpx.AsyncClient(
                transport=_make_mock_transport(MOCK_TEXT_RESPONSE)
            )
            response = await client.chat(messages=[{"role": "user", "content": "hi"}])
            assert response.id == "msg_mock_1"

    @pytest.mark.asyncio
    async def test_http_error_raises_llm_api_error(self):
        """non-retryable HTTP 에러는 LLMAPIError로 래핑되어 즉시 전파"""
        error_response = {
            "type": "error",
            "error": {"type": "authentication_error", "message": "invalid key"},
        }
        client = AnthropicClient(api_key="bad-key")
        client._http = httpx.AsyncClient(
            transport=_make_mock_transport(error_response, status_code=401)
        )
        with pytest.raises(LLMAPIError) as exc_info:
            await client.chat(messages=[{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 401
        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.retryable is False
        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        """429 Rate Limit 시 재시도 후 성공"""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(status_code=429, json={"error": "rate limited"})
            return httpx.Response(status_code=200, json=MOCK_TEXT_RESPONSE)

        client = AnthropicClient(api_key="fake-key")
        client.max_retries = 3
        client.retry_base_delay = 0.01  # 테스트 속도를 위해 짧은 대기
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = await client.chat(
            messages=[{"role": "user", "content": "hi"}]
        )
        assert response.stop_reason == StopReason.END_TURN
        assert call_count == 3  # 2번 실패 + 1번 성공
        await client.close()

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        """재시도 횟수 소진 시 LLMAPIError 발생"""
        client = AnthropicClient(api_key="fake-key")
        client.max_retries = 2
        client.retry_base_delay = 0.01
        client._http = httpx.AsyncClient(
            transport=_make_mock_transport({"error": "overloaded"}, status_code=529)
        )

        with pytest.raises(LLMAPIError) as exc_info:
            await client.chat(messages=[{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 529
        assert exc_info.value.retryable is True
        await client.close()

    @pytest.mark.asyncio
    async def test_retry_on_500(self):
        """500 서버 에러 시 재시도 후 성공"""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(status_code=500, json={"error": "server error"})
            return httpx.Response(status_code=200, json=MOCK_TEXT_RESPONSE)

        client = AnthropicClient(api_key="fake-key")
        client.max_retries = 3
        client.retry_base_delay = 0.01
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = await client.chat(
            messages=[{"role": "user", "content": "hi"}]
        )
        assert response.stop_reason == StopReason.END_TURN
        assert call_count == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_stream_text_delta(self):
        captured_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(json.loads(request.content))
            return httpx.Response(
                status_code=200,
                headers={"content-type": "text/event-stream"},
                content=MOCK_STREAM_RESPONSE.encode("utf-8"),
            )

        client = AnthropicClient(api_key="fake-key")
        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        chunks = [
            chunk
            async for chunk in client.chat_stream(
                messages=[{"role": "user", "content": "안녕"}]
            )
        ]

        text_deltas = [chunk.delta_text for chunk in chunks if chunk.delta_text]
        assert text_deltas == ["안", "녕"]

        final_chunk = chunks[-1]
        assert final_chunk.response is not None
        assert final_chunk.response.final_text() == "안녕"
        assert final_chunk.response.usage.input_tokens == 11
        assert final_chunk.response.usage.output_tokens == 2

        assert captured_requests[0]["stream"] is True
        await client.close()
