"""
AgentRuntime 실행 루프 테스트
- mock client + mock tool로 전체 루프 검증
python -m pytest tests/test_runtime.py -v
"""

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from sonya_core.llm.errors import LLMAPIError
from sonya_core.llm.models import LLMResponse, LLMStreamChunk, StopReason, Usage
from sonya_core.runtime.agent import AgentRuntime
from sonya_core.tools.base import BaseTool
from sonya_core.tools.registry import ToolRegistry


# ── 테스트용 Tool ──────────────────────────────────────────────


class AddInput(BaseModel):
    a: int = Field(description="첫 번째 숫자")
    b: int = Field(description="두 번째 숫자")


class AddOutput(BaseModel):
    result: int


class AddTool(BaseTool[AddInput, AddOutput]):
    name = "add"
    description = "두 숫자를 더한다"

    async def execute(self, input: AddInput) -> AddOutput:
        return AddOutput(result=input.a + input.b)


# ── 헬퍼 ──────────────────────────────────────────────────────


def _make_text_response(text: str, msg_id: str = "msg_1") -> LLMResponse:
    """end_turn 텍스트 응답 생성"""
    return LLMResponse(
        id=msg_id,
        model="mock",
        stop_reason=StopReason.END_TURN,
        content=[{"type": "text", "text": text}],
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def _make_tool_use_response(
    tool_name: str,
    tool_input: dict,
    tool_use_id: str = "tu_1",
    text: str = "",
    msg_id: str = "msg_2",
) -> LLMResponse:
    """tool_use 응답 생성"""
    content = []
    if text:
        content.append({"type": "text", "text": text})
    content.append(
        {
            "type": "tool_use",
            "id": tool_use_id,
            "name": tool_name,
            "input": tool_input,
        }
    )
    return LLMResponse(
        id=msg_id,
        model="mock",
        stop_reason=StopReason.TOOL_USE,
        content=content,
        usage=Usage(input_tokens=15, output_tokens=10),
    )


def _make_stream(*chunks: LLMStreamChunk):
    async def _gen():
        for chunk in chunks:
            yield chunk

    return _gen()


class _MockStreamingClient:
    def __init__(self, streams: list[list[LLMStreamChunk]]):
        self._streams = streams
        self.stream_calls = 0

    @property
    def provider(self) -> str:
        return "mock"

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        raise RuntimeError("chat()은 이 테스트에서 사용하지 않습니다.")

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None):
        stream = self._streams[self.stream_calls]
        self.stream_calls += 1
        for chunk in stream:
            yield chunk

    async def close(self) -> None:
        return


# ── 테스트 ─────────────────────────────────────────────────────


class TestAgentRuntime:
    @pytest.mark.asyncio
    async def test_simple_text_response(self):
        """Tool 호출 없이 바로 텍스트 응답하는 케이스"""
        mock_client = AsyncMock()
        mock_client.chat.return_value = _make_text_response("안녕하세요!")

        registry = ToolRegistry()
        agent = AgentRuntime(mock_client, registry)

        result = await agent.run("안녕")
        assert result == "안녕하세요!"
        assert mock_client.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_tool_use_loop(self):
        """Tool 호출 → 결과 → 최종 텍스트 응답 루프"""
        mock_client = AsyncMock()
        # 첫 호출: tool_use 요청
        # 두 번째 호출: 최종 텍스트 응답
        mock_client.chat.side_effect = [
            _make_tool_use_response("add", {"a": 3, "b": 5}),
            _make_text_response("3 + 5 = 8 입니다."),
        ]

        registry = ToolRegistry()
        registry.register(AddTool())
        agent = AgentRuntime(mock_client, registry)

        result = await agent.run("3 더하기 5는?")
        assert "8" in result
        assert mock_client.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self):
        """여러 번의 Tool 호출이 필요한 케이스"""
        mock_client = AsyncMock()
        mock_client.chat.side_effect = [
            _make_tool_use_response("add", {"a": 1, "b": 2}, tool_use_id="tu_1"),
            _make_tool_use_response("add", {"a": 3, "b": 4}, tool_use_id="tu_2"),
            _make_text_response("1+2=3, 3+4=7"),
        ]

        registry = ToolRegistry()
        registry.register(AddTool())
        agent = AgentRuntime(mock_client, registry)

        _ = await agent.run("1+2와 3+4를 계산해줘")
        assert mock_client.chat.call_count == 3

    @pytest.mark.asyncio
    async def test_max_iterations_exceeded(self):
        """무한 루프 방지: max_iterations 초과 시 RuntimeError"""
        mock_client = AsyncMock()
        # 항상 tool_use를 반환해서 루프가 끝나지 않게
        mock_client.chat.return_value = _make_tool_use_response("add", {"a": 1, "b": 1})

        registry = ToolRegistry()
        registry.register(AddTool())
        agent = AgentRuntime(mock_client, registry, max_iterations=3)

        with pytest.raises(RuntimeError, match="최대 반복 횟수"):
            await agent.run("무한 루프 테스트")

        assert mock_client.chat.call_count == 3

    @pytest.mark.asyncio
    async def test_history_is_maintained(self):
        """멀티턴 대화에서 히스토리가 유지되는지 검증"""
        mock_client = AsyncMock()
        mock_client.chat.side_effect = [
            _make_text_response("첫 번째 응답"),
            _make_text_response("두 번째 응답"),
        ]

        registry = ToolRegistry()
        agent = AgentRuntime(mock_client, registry)

        await agent.run("첫 번째 질문")
        await agent.run("두 번째 질문")

        # user 2개 + assistant 2개 = 4개
        assert len(agent.history) == 4
        assert agent.history[0].role == "user"
        assert agent.history[1].role == "assistant"
        assert agent.history[2].role == "user"
        assert agent.history[3].role == "assistant"

    @pytest.mark.asyncio
    async def test_reset_clears_history(self):
        """reset()이 히스토리를 비우는지 검증"""
        mock_client = AsyncMock()
        mock_client.chat.return_value = _make_text_response("응답")

        registry = ToolRegistry()
        agent = AgentRuntime(mock_client, registry)

        await agent.run("질문")
        assert len(agent.history) > 0

        agent.reset()
        assert len(agent.history) == 0

    @pytest.mark.asyncio
    async def test_tool_result_in_history(self):
        """Tool 실행 결과가 히스토리에 올바르게 추가되는지 검증"""
        mock_client = AsyncMock()
        mock_client.chat.side_effect = [
            _make_tool_use_response("add", {"a": 10, "b": 20}),
            _make_text_response("30입니다"),
        ]

        registry = ToolRegistry()
        registry.register(AddTool())
        agent = AgentRuntime(mock_client, registry)

        await agent.run("10 + 20?")

        # user(질문) → assistant(tool_use) → user(tool_result) → assistant(text)
        assert len(agent.history) == 4
        # tool_result 메시지 확인
        tool_result_msg = agent.history[2]
        assert tool_result_msg.role == "user"
        # content는 ToolResultBlock 리스트
        assert tool_result_msg.content[0].type == "tool_result"

    @pytest.mark.asyncio
    async def test_no_tools_registered(self):
        """Tool 없이 텍스트만 주고받는 케이스"""
        mock_client = AsyncMock()
        mock_client.chat.return_value = _make_text_response("도움이 필요하신가요?")

        registry = ToolRegistry()  # Tool 없음
        agent = AgentRuntime(mock_client, registry)

        result = await agent.run("안녕")
        assert result == "도움이 필요하신가요?"

        # tools=None으로 호출되었는지 확인
        call_kwargs = mock_client.chat.call_args
        assert call_kwargs.kwargs.get("tools") is None

    @pytest.mark.asyncio
    async def test_max_tokens_returns_partial(self):
        """max_tokens 도달 시 잘린 응답을 반환"""
        mock_client = AsyncMock()
        mock_client.chat.return_value = LLMResponse(
            id="msg_trunc",
            model="mock",
            stop_reason=StopReason.MAX_TOKENS,
            content=[{"type": "text", "text": "잘린 응답..."}],
            usage=Usage(input_tokens=10, output_tokens=4096),
        )

        registry = ToolRegistry()
        agent = AgentRuntime(mock_client, registry)
        result = await agent.run("긴 질문")
        assert result == "잘린 응답..."

    @pytest.mark.asyncio
    async def test_run_stream_simple_text(self):
        response = _make_text_response("안녕하세요")
        streaming_client = _MockStreamingClient(
            streams=[
                [
                    LLMStreamChunk(delta_text="안"),
                    LLMStreamChunk(delta_text="녕"),
                    LLMStreamChunk(response=response),
                ]
            ]
        )

        registry = ToolRegistry()
        agent = AgentRuntime(streaming_client, registry)

        chunks = [chunk async for chunk in agent.run_stream("인사해줘")]
        assert chunks == ["안", "녕"]
        assert streaming_client.stream_calls == 1

    @pytest.mark.asyncio
    async def test_run_stream_with_tool_loop(self):
        first_response = _make_tool_use_response(
            tool_name="add",
            tool_input={"a": 2, "b": 3},
            tool_use_id="tu_stream_1",
        )
        second_response = _make_text_response("결과는 5입니다")
        streaming_client = _MockStreamingClient(
            streams=[
                [
                    LLMStreamChunk(delta_text="계"),
                    LLMStreamChunk(delta_text="산"),
                    LLMStreamChunk(response=first_response),
                ],
                [
                    LLMStreamChunk(delta_text="5"),
                    LLMStreamChunk(response=second_response),
                ],
            ]
        )

        registry = ToolRegistry()
        registry.register(AddTool())
        agent = AgentRuntime(streaming_client, registry)

        chunks = [chunk async for chunk in agent.run_stream("2+3 계산")]
        assert chunks == ["계", "산", "5"]
        assert streaming_client.stream_calls == 2

        tool_result_msg = agent.history[2]
        assert tool_result_msg.role == "user"
        assert tool_result_msg.content[0].type == "tool_result"

    @pytest.mark.asyncio
    async def test_llm_api_error_wrapped_as_runtime_error(self):
        """LLMAPIError 발생 시 RuntimeError로 래핑"""
        mock_client = AsyncMock()
        mock_client.chat.side_effect = LLMAPIError(
            status_code=500,
            provider="mock",
            message="Internal Server Error",
        )

        registry = ToolRegistry()
        agent = AgentRuntime(mock_client, registry)

        with pytest.raises(RuntimeError, match="LLM API 호출에 실패했습니다"):
            await agent.run("테스트")

    @pytest.mark.asyncio
    async def test_llm_api_error_preserves_info(self):
        """RuntimeError에 provider와 status_code 정보가 포함되는지 검증"""
        mock_client = AsyncMock()
        mock_client.chat.side_effect = LLMAPIError(
            status_code=429,
            provider="anthropic",
            message="Rate limited",
        )

        registry = ToolRegistry()
        agent = AgentRuntime(mock_client, registry)

        with pytest.raises(RuntimeError, match="anthropic.*429"):
            await agent.run("테스트")
