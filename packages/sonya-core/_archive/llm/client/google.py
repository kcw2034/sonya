"""
Google Gemini API 클라이언트
- httpx.AsyncClient 기반 (google-genai SDK 미사용, 의존성 최소화)
- generateContent API + function calling 지원
- BaseLLMClient 구현체
"""

from __future__ import annotations

import logging
import os

import httpx

from ..base import BaseLLMClient
from ...utils.llm.client.google import (
    _convert_messages,
    _convert_tools,
    _parse_response,
)
from ..models import LLMResponse

logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiClient(BaseLLMClient):
    """
    Google Gemini API 비동기 클라이언트

    사용법:
        async with GeminiClient(api_key="...") as client:
            response = await client.chat(messages=[...], tools=[...])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        system: str | None = None,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "api_key가 필요합니다. 직접 전달하거나 GEMINI_API_KEY 환경변수를 설정하세요."
            )
        self.model = model
        self.max_tokens = max_tokens
        self.system = system
        self.max_retries = max_retries
        self._http: httpx.AsyncClient | None = None
        # Gemini는 functionCall에 ID가 없으므로 합성 ID↔이름 매핑을 유지
        self._call_id_map: dict[str, str] = {}

    @property
    def provider(self) -> str:
        return "gemini"

    async def _get_http(self) -> httpx.AsyncClient:
        """httpx 클라이언트 lazy 초기화"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._http

    async def _chat_impl(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Gemini generateContent API 호출

        Anthropic 포맷의 messages와 tools를 받아서
        내부적으로 Gemini 포맷으로 변환 후 API를 호출한다.
        """
        http = await self._get_http()

        url = GEMINI_API_URL.format(model=self.model)

        body: dict = {
            "contents": _convert_messages(messages, self._call_id_map),
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
            },
        }

        if self.system:
            body["systemInstruction"] = {
                "parts": [{"text": self.system}],
            }

        if tools:
            body["tools"] = _convert_tools(tools)

        logger.debug(
            f"[gemini] chat request: model={self.model}, messages={len(messages)}"
        )

        response = await http.post(
            url,
            json=body,
            params={"key": self.api_key},
        )
        response.raise_for_status()

        result = _parse_response(response.json(), self.model, self._call_id_map)
        logger.debug(
            f"[gemini] response: stop_reason={result.stop_reason.value}, "
            f"usage=({result.usage.input_tokens}in/{result.usage.output_tokens}out)"
        )
        return result

    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
