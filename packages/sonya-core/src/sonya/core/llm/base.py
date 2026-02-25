"""
LLM 클라이언트 추상 인터페이스
- 모든 LLM Provider 클라이언트의 베이스 클래스
- Provider별 구현체는 이 인터페이스를 따른다
- 지수 백오프 재시도 로직 내장
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod

import httpx

from .errors import LLMAPIError, RETRYABLE_STATUS_CODES
from .models import LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """
    LLM Provider 추상 클라이언트

    모든 Provider 구현체는 이 클래스를 상속하고,
    chat()에서 Provider 고유 API를 호출한 뒤 LLMResponse로 변환하여 반환한다.

    재시도 로직:
        chat()에서 httpx.HTTPStatusError 발생 시 retryable 상태 코드이면
        지수 백오프로 max_retries까지 재시도한다.

    사용법:
        async with SomeClient(api_key="...") as client:
            response = await client.chat(messages=[...], tools=[...])
    """

    # 재시도 설정 — 서브클래스에서 오버라이드 가능
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
    retry_factor: float = 2.0

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider 이름 반환 (예: 'anthropic', 'openai')"""
        ...

    @abstractmethod
    async def _chat_impl(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        실제 LLM API 호출 (서브클래스가 구현)

        Args:
            messages: Provider 포맷의 메시지 리스트
            tools: Tool 스키마 리스트 (Provider 포맷)

        Returns:
            LLMResponse — 통합 응답 모델
        """
        ...

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        재시도 래퍼가 포함된 LLM API 호출

        httpx.HTTPStatusError 중 retryable 상태 코드(429, 5xx)는
        지수 백오프로 재시도한다. 그 외 에러는 LLMAPIError로 래핑하여 즉시 전파.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self._chat_impl(messages=messages, tools=tools)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                last_error = e

                if status not in RETRYABLE_STATUS_CODES or attempt >= self.max_retries:
                    raise LLMAPIError(
                        status_code=status,
                        provider=self.provider,
                        message=str(e),
                    ) from e

                delay = min(
                    self.retry_base_delay * (self.retry_factor ** attempt),
                    self.retry_max_delay,
                )
                logger.warning(
                    f"[{self.provider}] API error {status}, "
                    f"재시도 {attempt + 1}/{self.max_retries} (대기 {delay:.1f}s)"
                )
                await asyncio.sleep(delay)

        # 이 지점에 도달하면 안 되지만 안전 장치
        raise LLMAPIError(
            status_code=0,
            provider=self.provider,
            message=f"재시도 소진: {last_error}",
        )

    @abstractmethod
    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        ...

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        response = await self.chat(messages=messages, tools=tools)

        text = response.final_text()
        if text:
            yield LLMStreamChunk(delta_text=text)

        yield LLMStreamChunk(response=response)

    async def __aenter__(self) -> BaseLLMClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
