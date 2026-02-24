"""
LLM 클라이언트 추상 인터페이스
- 모든 LLM Provider 클라이언트의 베이스 클래스
- Provider별 구현체는 이 인터페이스를 따른다
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import LLMResponse


class BaseLLMClient(ABC):
    """
    LLM Provider 추상 클라이언트

    모든 Provider 구현체는 이 클래스를 상속하고,
    chat()에서 Provider 고유 API를 호출한 뒤 LLMResponse로 변환하여 반환한다.

    사용법:
        async with SomeClient(api_key="...") as client:
            response = await client.chat(messages=[...], tools=[...])
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider 이름 반환 (예: 'anthropic', 'openai')"""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        LLM API 호출

        Args:
            messages: Provider 포맷의 메시지 리스트
            tools: Tool 스키마 리스트 (Provider 포맷)

        Returns:
            LLMResponse — 통합 응답 모델
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        ...

    async def __aenter__(self) -> BaseLLMClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
