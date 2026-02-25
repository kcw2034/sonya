"""
LLM 모델 직렬화/역직렬화 테스트
python -m pytest tests/test_llm_models.py -v
"""

from sonya.core.llm.models import (
    ContentBlock,
    LLMStreamChunk,
    LLMResponse,
    Message,
    StopReason,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)


class TestContentBlocks:
    def test_text_block(self):
        block = TextBlock(text="안녕하세요")
        assert block.type == "text"
        assert block.text == "안녕하세요"

    def test_tool_use_block(self):
        block = ToolUseBlock(id="tu_1", name="web_search", input={"query": "날씨"})
        assert block.type == "tool_use"
        assert block.name == "web_search"
        assert block.input == {"query": "날씨"}

    def test_tool_result_block(self):
        block = ToolResultBlock(tool_use_id="tu_1", content='{"temp": 20}')
        assert block.type == "tool_result"
        assert block.tool_use_id == "tu_1"

    def test_discriminated_union_parsing(self):
        """type 필드 기반으로 올바른 블록 타입이 선택되는지 검증"""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(ContentBlock)

        text = adapter.validate_python({"type": "text", "text": "hello"})
        assert isinstance(text, TextBlock)

        tool_use = adapter.validate_python(
            {"type": "tool_use", "id": "tu_1", "name": "calc", "input": {"x": 1}}
        )
        assert isinstance(tool_use, ToolUseBlock)

        tool_result = adapter.validate_python(
            {"type": "tool_result", "tool_use_id": "tu_1", "content": "42"}
        )
        assert isinstance(tool_result, ToolResultBlock)


class TestMessage:
    def test_str_content_to_api_dict(self):
        msg = Message(role="user", content="안녕")
        d = msg.to_api_dict()
        assert d == {"role": "user", "content": "안녕"}

    def test_block_content_to_api_dict(self):
        msg = Message(
            role="assistant",
            content=[
                TextBlock(text="검색해볼게요"),
                ToolUseBlock(id="tu_1", name="web_search", input={"query": "날씨"}),
            ],
        )
        d = msg.to_api_dict()
        assert d["role"] == "assistant"
        assert len(d["content"]) == 2
        assert d["content"][0]["type"] == "text"
        assert d["content"][1]["type"] == "tool_use"

    def test_tool_result_message(self):
        msg = Message(
            role="user",
            content=[
                ToolResultBlock(tool_use_id="tu_1", content='{"temp": 20}'),
            ],
        )
        d = msg.to_api_dict()
        assert d["role"] == "user"
        assert d["content"][0]["type"] == "tool_result"


class TestStopReason:
    def test_enum_values(self):
        assert StopReason.END_TURN == "end_turn"
        assert StopReason.TOOL_USE == "tool_use"
        assert StopReason.MAX_TOKENS == "max_tokens"

    def test_from_string(self):
        assert StopReason("end_turn") == StopReason.END_TURN


class TestLLMResponse:
    SAMPLE_API_RESPONSE = {
        "id": "msg_123",
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "end_turn",
        "content": [
            {"type": "text", "text": "서울 날씨는 맑습니다."},
        ],
        "usage": {"input_tokens": 50, "output_tokens": 20},
    }

    TOOL_USE_API_RESPONSE = {
        "id": "msg_456",
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "tool_use",
        "content": [
            {"type": "text", "text": "날씨를 검색해보겠습니다."},
            {
                "type": "tool_use",
                "id": "tu_1",
                "name": "web_search",
                "input": {"query": "서울 날씨"},
            },
        ],
        "usage": {"input_tokens": 60, "output_tokens": 30},
    }

    def test_from_api_response_text(self):
        resp = LLMResponse.from_api_response(self.SAMPLE_API_RESPONSE)
        assert resp.id == "msg_123"
        assert resp.stop_reason == StopReason.END_TURN
        assert resp.final_text() == "서울 날씨는 맑습니다."
        assert resp.usage.input_tokens == 50

    def test_from_api_response_tool_use(self):
        resp = LLMResponse.from_api_response(self.TOOL_USE_API_RESPONSE)
        assert resp.stop_reason == StopReason.TOOL_USE
        tool_blocks = resp.tool_use_blocks()
        assert len(tool_blocks) == 1
        assert tool_blocks[0].name == "web_search"
        assert resp.final_text() == "날씨를 검색해보겠습니다."

    def test_text_blocks_filter(self):
        resp = LLMResponse.from_api_response(self.TOOL_USE_API_RESPONSE)
        texts = resp.text_blocks()
        assert len(texts) == 1
        assert texts[0].text == "날씨를 검색해보겠습니다."

    def test_empty_content(self):
        data = {
            "id": "msg_789",
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "content": [],
            "usage": {"input_tokens": 10, "output_tokens": 0},
        }
        resp = LLMResponse.from_api_response(data)
        assert resp.final_text() == ""
        assert resp.tool_use_blocks() == []


class TestLLMStreamChunk:
    def test_delta_text_chunk(self):
        chunk = LLMStreamChunk(delta_text="안")
        assert chunk.delta_text == "안"
        assert chunk.response is None

    def test_response_chunk(self):
        response = LLMResponse.from_api_response(
            {
                "id": "msg_stream_1",
                "model": "claude-sonnet-4-20250514",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "완료"}],
                "usage": {"input_tokens": 3, "output_tokens": 1},
            }
        )
        chunk = LLMStreamChunk(response=response)
        assert chunk.delta_text is None
        assert chunk.response is not None
        assert chunk.response.final_text() == "완료"
