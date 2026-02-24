"""
Google Gemini API 클라이언트
- httpx.AsyncClient 기반 (google-genai SDK 미사용, 의존성 최소화)
- generateContent API + function calling 지원
- BaseLLMClient 구현체
"""

from __future__ import annotations

import json
import os
import uuid

import httpx

from ..base import BaseLLMClient
from ..models import LLMResponse, StopReason, Usage

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
        model: str = "gemini-3-flash-preview",
        max_tokens: int = 4096,
        system: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "api_key가 필요합니다. 직접 전달하거나 GEMINI_API_KEY 환경변수를 설정하세요."
            )
        self.model = model
        self.max_tokens = max_tokens
        self.system = system
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

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """
        Anthropic 포맷 메시지를 Gemini 포맷으로 변환

        Anthropic:
            {"role": "user", "content": "text"}
            {"role": "assistant", "content": [{"type": "tool_use", ...}]}
            {"role": "user", "content": [{"type": "tool_result", ...}]}
        Gemini:
            {"role": "user", "parts": [{"text": "..."}]}
            {"role": "model", "parts": [{"functionCall": {"name": ..., "args": ...}}]}
            {"role": "user", "parts": [{"functionResponse": {"name": ..., "response": ...}}]}
        """
        # 먼저 tool_use 블록에서 id→name 매핑 구축 (tool_result 변환에 필요)
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    self._call_id_map[block["id"]] = block["name"]

        gemini_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Gemini는 "assistant" 대신 "model" 사용
            gemini_role = "model" if role == "assistant" else "user"

            # 단순 텍스트 메시지
            if isinstance(content, str):
                gemini_messages.append(
                    {
                        "role": gemini_role,
                        "parts": [{"text": content}],
                    }
                )
                continue

            # content가 블록 리스트인 경우
            if isinstance(content, list):
                parts = []
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    if block.get("type") == "text":
                        parts.append({"text": block["text"]})

                    elif block.get("type") == "tool_use":
                        parts.append(
                            {
                                "functionCall": {
                                    "name": block["name"],
                                    "args": block.get("input", {}),
                                },
                            }
                        )

                    elif block.get("type") == "tool_result":
                        tool_use_id = block["tool_use_id"]
                        fn_name = self._call_id_map.get(tool_use_id, "unknown")
                        # content를 dict로 파싱 시도, 실패 시 문자열 래핑
                        raw_content = block.get("content", "")
                        try:
                            response_data = (
                                json.loads(raw_content)
                                if isinstance(raw_content, str)
                                else raw_content
                            )
                        except (json.JSONDecodeError, TypeError):
                            response_data = {"result": raw_content}

                        parts.append(
                            {
                                "functionResponse": {
                                    "name": fn_name,
                                    "response": response_data,
                                },
                            }
                        )

                if parts:
                    gemini_messages.append(
                        {
                            "role": gemini_role,
                            "parts": parts,
                        }
                    )
                continue

            # 폴백
            gemini_messages.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": str(content)}],
                }
            )

        return gemini_messages

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """
        Anthropic 포맷 Tool 스키마를 Gemini functionDeclarations로 변환

        Anthropic: {"name": "...", "description": "...", "input_schema": {...}}
        Gemini:    {"functionDeclarations": [{"name": "...", "description": "...", "parameters": {...}}]}
        """
        declarations = []
        for tool in tools:
            decl: dict = {
                "name": tool["name"],
                "description": tool.get("description", ""),
            }
            params = tool.get("input_schema", {})
            if params:
                decl["parameters"] = params
            declarations.append(decl)
        return [{"functionDeclarations": declarations}]

    async def chat(
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
            "contents": self._convert_messages(messages),
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
            },
        }

        if self.system:
            body["systemInstruction"] = {
                "parts": [{"text": self.system}],
            }

        if tools:
            body["tools"] = self._convert_tools(tools)

        response = await http.post(
            url,
            json=body,
            params={"key": self.api_key},
        )
        response.raise_for_status()

        return self._parse_response(response.json())

    def _parse_response(self, data: dict) -> LLMResponse:
        """
        Gemini API 응답을 LLMResponse로 변환

        Gemini finishReason → StopReason 매핑:
            "STOP" + functionCall parts → TOOL_USE
            "STOP" (텍스트만) → END_TURN
            "MAX_TOKENS" → MAX_TOKENS
        """
        candidate = data["candidates"][0]
        parts = candidate.get("content", {}).get("parts", [])
        finish_reason = candidate.get("finishReason", "STOP")

        # content 블록 생성 (Anthropic 통합 포맷)
        content_blocks = []
        has_function_call = False

        for part in parts:
            if "text" in part:
                content_blocks.append(
                    {
                        "type": "text",
                        "text": part["text"],
                    }
                )
            elif "functionCall" in part:
                has_function_call = True
                fc = part["functionCall"]
                # Gemini는 functionCall에 ID가 없으므로 합성
                call_id = f"gemini_{uuid.uuid4().hex[:12]}"
                self._call_id_map[call_id] = fc["name"]
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": fc["name"],
                        "input": fc.get("args", {}),
                    }
                )

        # StopReason 결정
        if has_function_call:
            stop_reason = StopReason.TOOL_USE
        elif finish_reason == "MAX_TOKENS":
            stop_reason = StopReason.MAX_TOKENS
        else:
            stop_reason = StopReason.END_TURN

        # Usage 변환
        usage_data = data.get("usageMetadata", {})
        usage = Usage(
            input_tokens=usage_data.get("promptTokenCount", 0),
            output_tokens=usage_data.get("candidatesTokenCount", 0),
        )

        return LLMResponse(
            id=data.get("id", f"gemini_{uuid.uuid4().hex[:8]}"),
            model=data.get("modelVersion", self.model),
            stop_reason=stop_reason,
            content=content_blocks,
            usage=usage,
        )

    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
