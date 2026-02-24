"""
에이전트 실행 루프
- user → LLM → tool_use → tool_result → LLM 반복
- max_iterations 초과 시 RuntimeError
- ToolContext로 Tool 간 데이터 공유
"""

from __future__ import annotations

import logging

from ..llm.base import BaseLLMClient
from ..llm.models import Message, StopReason, ToolResultBlock
from ..tools.context import ToolContext
from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    LLM ↔ Tool 실행 루프를 관리하는 에이전트 런타임

    사용법:
        async with AnthropicClient(api_key="...") as client:  # 또는 OpenAIClient
            registry = ToolRegistry()
            registry.register(MyTool())

            agent = AgentRuntime(client, registry)
            answer = await agent.run("서울 날씨 알려줘")
    """

    def __init__(
        self,
        client: BaseLLMClient,
        registry: ToolRegistry,
        max_iterations: int = 10,
    ):
        self.client = client
        self.registry = registry
        self.max_iterations = max_iterations
        self._history: list[Message] = []

    async def run(self, user_message: str) -> str:
        """
        사용자 메시지를 받아 최종 텍스트 응답을 반환

        Tool 호출이 필요하면 자동으로 실행 후 LLM에 결과를 돌려보내는
        루프를 max_iterations까지 반복한다.
        ToolContext는 run() 호출 동안 유지되어 Tool 간 데이터 공유에 사용된다.
        """
        # 1. user 메시지 추가
        self._history.append(Message(role="user", content=user_message))

        tools = self.registry.schemas() if len(self.registry) > 0 else None

        # run 스코프의 ToolContext 생성
        ctx = ToolContext()

        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{self.max_iterations}")

            # 2. LLM 호출
            api_messages = [m.to_api_dict() for m in self._history]
            response = await self.client.chat(messages=api_messages, tools=tools)

            # assistant 응답을 history에 추가
            self._history.append(Message(
                role="assistant",
                content=response.content,
            ))

            # 3. end_turn → 최종 텍스트 반환
            if response.stop_reason == StopReason.END_TURN:
                return response.final_text()

            # 4. max_tokens → 잘린 응답 반환
            if response.stop_reason == StopReason.MAX_TOKENS:
                logger.warning("max_tokens에 도달하여 응답이 잘렸습니다.")
                return response.final_text()

            # 5. tool_use → Tool 실행 후 결과를 history에 추가
            if response.stop_reason == StopReason.TOOL_USE:
                tool_use_blocks = response.tool_use_blocks()
                tool_calls = [
                    {"id": b.id, "name": b.name, "input": b.input}
                    for b in tool_use_blocks
                ]

                results = await self.registry.execute_many(tool_calls, ctx=ctx)

                # tool_result 블록들을 user 메시지로 추가
                result_blocks = []
                for r in results:
                    content = r.to_llm_format()["content"]
                    # ToolContext에 데이터가 있으면 요약 정보를 추가
                    if ctx.keys():
                        summary = ctx.summary()
                        content += f"\n[ToolContext: {summary}]"
                    result_blocks.append(
                        ToolResultBlock(
                            tool_use_id=r.tool_use_id,
                            content=content,
                        )
                    )
                self._history.append(Message(
                    role="user",
                    content=result_blocks,
                ))

        raise RuntimeError(
            f"최대 반복 횟수({self.max_iterations})를 초과했습니다. "
            "Tool 호출 루프가 종료되지 않았습니다."
        )

    def reset(self) -> None:
        """대화 히스토리 초기화"""
        self._history.clear()

    @property
    def history(self) -> list[Message]:
        """현재 대화 히스토리 (읽기 전용)"""
        return list(self._history)
