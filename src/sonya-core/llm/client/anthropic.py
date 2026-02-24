"""
Anthropic API 클라이언트
- httpx.AsyncClient 기반 (anthropic SDK 미사용, 의존성 최소화)
- BaseLLMClient 구현체
- async context manager 지원
"""

from __future__ import annotations

import os

import httpx

from ..base import BaseLLMClient
from ..models import LLMResponse

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicClient(BaseLLMClient):
    """
    Anthropic Messages API 비동기 클라이언트

    사용법:
        async with AnthropicClient(api_key="...") as client:
            response = await client.chat(messages=[...], tools=[...])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        system: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "api_key가 필요합니다. 직접 전달하거나 ANTHROPIC_API_KEY 환경변수를 설정하세요."
            )
        self.model = model
        self.max_tokens = max_tokens
        self.system = system
        self._http: httpx.AsyncClient | None = None

    @property
    def provider(self) -> str:
        return "anthropic"

    async def _get_http(self) -> httpx.AsyncClient:
        """httpx 클라이언트 lazy 초기화"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._http

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Anthropic Messages API 호출

        Args:
            messages: API 포맷 메시지 리스트 (Message.to_api_dict() 결과)
            tools: Tool 스키마 리스트 (ToolRegistry.schemas() 결과)

        Returns:
            LLMResponse 파싱된 응답
        """
        http = await self._get_http()

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if self.system:
            body["system"] = self.system
        if tools:
            body["tools"] = tools

        response = await http.post(ANTHROPIC_API_URL, json=body)
        response.raise_for_status()

        return LLMResponse.from_api_response(response.json())

    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def __aenter__(self) -> AnthropicClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
