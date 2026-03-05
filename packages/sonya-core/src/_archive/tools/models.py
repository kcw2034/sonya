"""
Tool 실행 결과 모델
- Tool이 반환하는 성공/실패 결과를 통일된 구조로 래핑
- Anthropic API tool_result 포맷 변환 지원
- _raw: LLM에 보내지 않는 원본 데이터 (벡터, 텐서 등)
- llm_summary: output 대신 LLM에 보낼 커스텀 요약
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr


class ToolResult(BaseModel):
    """
    Tool 실행 결과 래퍼

    BaseTool.safe_execute()에서 생성되며,
    성공 시 output에 결과를, 실패 시 error에 메시지를 담는다.

    _raw: LLM에 보내지 않는 원본 데이터. Pydantic 직렬화에서 제외됨.
    llm_summary: output 대신 LLM에 보낼 커스텀 요약문.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    tool_use_id: str  # Anthropic API가 부여하는 tool_use 식별자
    success: bool
    output: Any = None
    error: str | None = None
    llm_summary: str | None = None

    _raw: Any = PrivateAttr(default=None)

    @classmethod
    def from_output(
        cls,
        tool_name: str,
        tool_use_id: str,
        output: Any,
        *,
        raw: Any = None,
        llm_summary: str | None = None,
    ) -> ToolResult:
        """팩토리 메서드 — output, raw, llm_summary를 한 번에 설정"""
        result = cls(
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            success=True,
            output=output,
            llm_summary=llm_summary,
        )
        result._raw = raw
        return result

    def to_llm_format(self) -> dict:
        """
        Anthropic API tool_result 포맷으로 변환

        llm_summary가 있으면 output 대신 사용.
        _raw는 포함하지 않음.

        Returns:
            {"type": "tool_result", "tool_use_id": ..., "content": ...}
        """
        if not self.success:
            content = f"Error: {self.error}"
        elif self.llm_summary is not None:
            content = self.llm_summary
        else:
            content = json.dumps(self.output, ensure_ascii=False, default=str)

        return {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": content,
        }
