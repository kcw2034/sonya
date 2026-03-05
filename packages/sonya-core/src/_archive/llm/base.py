"""
LLM 클라이언트 추상 인터페이스
- 모든 LLM Provider 클라이언트의 베이스 클래스
- Provider별 구현체는 이 인터페이스를 따른다
- 지수 백오프 재시도 로직 내장
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .error import LLMAPIError, RETRYABLE_STATUS_CODES, StructuredOutputError
from .models import LLMResponse, LLMStreamChunk
from .schema import _schema_to_json_schema

T = TypeVar("T", bound=BaseModel)

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
                    self.retry_base_delay * (self.retry_factor**attempt),
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

    async def chat_structured(
        self,
        messages: list[dict],
        output_schema: type[T],
    ) -> T:
        """
        LLM 응답을 지정된 Pydantic 스키마로 파싱하여 반환

        기본 구현은 tool-use 트릭을 사용한다:
        1. output_schema를 input_schema로 가진 가상 Tool을 정의
        2. tool_choice로 해당 Tool 강제 호출
        3. Tool input을 output_schema로 파싱

        Provider별 서브클래스에서 네이티브 방식으로 오버라이드할 수 있다.

        Args:
            messages: API 포맷 메시지 리스트
            output_schema: 응답을 파싱할 Pydantic 모델 클래스

        Returns:
            output_schema의 인스턴스

        Raises:
            StructuredOutputError: LLM 응답을 스키마로 파싱할 수 없을 때
        """
        tool_name = "_structured_output"
        json_schema = _schema_to_json_schema(output_schema)

        tool_def = {
            "name": tool_name,
            "description": (
                f"출력을 {output_schema.__name__} 스키마에 맞춰 구조화하여 반환합니다. "
                "반드시 이 도구를 호출하여 응답하세요."
            ),
            "input_schema": json_schema,
        }

        response = await self.chat(messages=messages, tools=[tool_def])

        tool_blocks = response.tool_use_blocks()
        if not tool_blocks:
            raise StructuredOutputError(
                schema_name=output_schema.__name__,
                raw_output=response.final_text(),
                message="LLM이 tool_use 블록을 반환하지 않았습니다.",
            )

        tool_input = tool_blocks[0].input
        try:
            return output_schema.model_validate(tool_input)
        except ValidationError as e:
            raise StructuredOutputError(
                schema_name=output_schema.__name__,
                raw_output=json.dumps(tool_input, ensure_ascii=False),
                message=str(e),
            ) from e

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
