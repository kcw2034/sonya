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
