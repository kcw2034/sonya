"""
LLM 메시지 & 응답 모델
- Anthropic API 메시지 포맷에 맞춘 Pydantic 모델
- ContentBlock: TextBlock, ToolUseBlock, ToolResultBlock의 discriminated union
- LLMResponse: API 응답 파싱 + 편의 헬퍼
"""

from __future__ import annotations

import enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """텍스트 콘텐츠 블록"""
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    """LLM이 Tool 호출을 요청하는 블록"""
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    """Tool 실행 결과를 LLM에 돌려보내는 블록"""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str


# Discriminated union — type 필드로 구분
ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]


class Message(BaseModel):
    """
    대화 메시지

    content는 편의상 str도 허용하지만,
    to_api_dict()에서는 Anthropic API 포맷으로 변환한다.
    """
    role: Literal["user", "assistant"]
    content: str | list[ContentBlock]

    def to_api_dict(self) -> dict:
        """Anthropic API messages 파라미터 포맷으로 직렬화"""
        if isinstance(self.content, str):
            return {"role": self.role, "content": self.content}
        return {
            "role": self.role,
            "content": [block.model_dump() for block in self.content],
        }


class StopReason(str, enum.Enum):
    """LLM 응답 종료 이유"""
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"


class Usage(BaseModel):
    """토큰 사용량"""
    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    """
    Anthropic API 응답을 파싱한 구조체

    raw JSON → LLMResponse.from_api_response() 로 생성
    """
    id: str
    model: str
    stop_reason: StopReason
    content: list[ContentBlock]
    usage: Usage

    def text_blocks(self) -> list[TextBlock]:
        """텍스트 블록만 필터"""
        return [b for b in self.content if isinstance(b, TextBlock)]

    def tool_use_blocks(self) -> list[ToolUseBlock]:
        """Tool 사용 블록만 필터"""
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    def final_text(self) -> str:
        """모든 텍스트 블록을 합쳐서 반환"""
        return "\n".join(b.text for b in self.text_blocks())

    @classmethod
    def from_api_response(cls, data: dict) -> LLMResponse:
        """Anthropic API raw JSON을 LLMResponse로 변환"""
        return cls(
            id=data["id"],
            model=data["model"],
            stop_reason=StopReason(data["stop_reason"]),
            content=data["content"],
            usage=Usage(**data["usage"]),
        )
