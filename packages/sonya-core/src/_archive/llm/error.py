"""
LLM API 에러 클래스
- Provider별 HTTP 에러를 의미 있는 예외로 래핑
- 재시도 가능 여부(retryable) 판별 포함
"""

from __future__ import annotations

# 재시도 대상 HTTP 상태 코드
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}


class LLMAPIError(Exception):
    """
    LLM API 호출 실패 시 발생하는 예외

    Attributes:
        status_code: HTTP 상태 코드
        provider: LLM Provider 이름 (예: 'anthropic', 'openai', 'gemini')
        message: 에러 메시지
        retryable: 재시도 가능 여부 (429, 5xx 등)
    """

    def __init__(
        self,
        status_code: int,
        provider: str,
        message: str,
        retryable: bool | None = None,
    ):
        self.status_code = status_code
        self.provider = provider
        self.message = message
        self.retryable = (
            retryable
            if retryable is not None
            else status_code in RETRYABLE_STATUS_CODES
        )
        super().__init__(
            f"[{provider}] API error {status_code}: {message}"
            f" (retryable={self.retryable})"
        )


class StructuredOutputError(Exception):
    """
    Structured Output 파싱 실패 시 발생하는 예외

    LLM 응답을 지정된 Pydantic 스키마로 파싱할 수 없을 때 발생한다.

    Attributes:
        schema_name: 대상 Pydantic 모델 클래스명
        raw_output: LLM이 반환한 원본 텍스트
        message: 파싱 실패 상세 메시지
    """

    def __init__(
        self,
        schema_name: str,
        raw_output: str,
        message: str,
    ):
        self.schema_name = schema_name
        self.raw_output = raw_output
        super().__init__(f"Structured output 파싱 실패 ({schema_name}): {message}")
