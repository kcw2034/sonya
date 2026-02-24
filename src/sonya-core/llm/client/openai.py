"""
OpenAI API 클라이언트
- httpx.AsyncClient 기반 (openai SDK 미사용, 의존성 최소화)
- Chat Completions API + function calling 지원
- BaseLLMClient 구현체
"""

from __future__ import annotations

import json
import os

import httpx

from ..base import BaseLLMClient
from ..models import LLMResponse, StopReason, Usage

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClient(BaseLLMClient):
    """
    OpenAI Chat Completions API 비동기 클라이언트

    사용법:
        async with OpenAIClient(api_key="...") as client:
            response = await client.chat(messages=[...], tools=[...])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.2",
        max_tokens: int = 4096,
        system: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "api_key가 필요합니다. 직접 전달하거나 OPENAI_API_KEY 환경변수를 설정하세요."
            )
        self.model = model
        self.max_tokens = max_tokens
        self.system = system
        self._http: httpx.AsyncClient | None = None

    @property
    def provider(self) -> str:
        return "openai"

    async def _get_http(self) -> httpx.AsyncClient:
        """httpx 클라이언트 lazy 초기화"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._http

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """
        Anthropic 포맷 메시지를 OpenAI 포맷으로 변환

        Anthropic:
            {"role": "user", "content": [{"type": "tool_result", ...}]}
            {"role": "assistant", "content": [{"type": "text", ...}, {"type": "tool_use", ...}]}
        OpenAI:
            {"role": "tool", "tool_call_id": "...", "content": "..."}
            {"role": "assistant", "content": "...", "tool_calls": [...]}
        """
        openai_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # 단순 텍스트 메시지
            if isinstance(content, str):
                openai_messages.append({"role": role, "content": content})
                continue

            # content가 블록 리스트인 경우
            if isinstance(content, list):
                # tool_result 블록만 있는 경우 → OpenAI "tool" role 메시지로 변환
                tool_results = [
                    b
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "tool_result"
                ]
                if tool_results:
                    for tr in tool_results:
                        openai_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tr["tool_use_id"],
                                "content": tr["content"],
                            }
                        )
                    continue

                # assistant 메시지: text + tool_use 블록 → OpenAI 포맷으로 변환
                text_parts = []
                tool_calls = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(
                                        block["input"], ensure_ascii=False
                                    ),
                                },
                            }
                        )

                assistant_msg: dict = {"role": role}
                assistant_msg["content"] = "\n".join(text_parts) if text_parts else None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                openai_messages.append(assistant_msg)
                continue

            # 기본 폴백
            openai_messages.append({"role": role, "content": str(content)})

        return openai_messages

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """
        Anthropic 포맷 Tool 스키마를 OpenAI 포맷으로 변환

        Anthropic: {"name": "...", "description": "...", "input_schema": {...}}
        OpenAI:    {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
            for tool in tools
        ]

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        OpenAI Chat Completions API 호출

        Anthropic 포맷의 messages와 tools를 받아서
        내부적으로 OpenAI 포맷으로 변환 후 API를 호출한다.
        """
        http = await self._get_http()

        openai_messages = self._convert_messages(messages)

        # system 메시지를 맨 앞에 삽입
        if self.system:
            openai_messages.insert(0, {"role": "system", "content": self.system})

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": openai_messages,
        }
        if tools:
            body["tools"] = self._convert_tools(tools)

        response = await http.post(OPENAI_API_URL, json=body)
        response.raise_for_status()

        return self._parse_response(response.json())

    def _parse_response(self, data: dict) -> LLMResponse:
        """
        OpenAI API 응답을 LLMResponse로 변환

        OpenAI finish_reason → StopReason 매핑:
            "stop" → END_TURN
            "tool_calls" → TOOL_USE
            "length" → MAX_TOKENS
        """
        choice = data["choices"][0]
        message = choice["message"]
        finish_reason = choice["finish_reason"]

        # StopReason 변환
        reason_map = {
            "stop": StopReason.END_TURN,
            "tool_calls": StopReason.TOOL_USE,
            "length": StopReason.MAX_TOKENS,
        }
        stop_reason = reason_map.get(finish_reason, StopReason.END_TURN)

        # content 블록 생성
        content_blocks = []

        # 텍스트 응답
        if message.get("content"):
            content_blocks.append(
                {
                    "type": "text",
                    "text": message["content"],
                }
            )

        # tool_calls → Anthropic tool_use 포맷으로 통합
        for tc in message.get("tool_calls", []):
            arguments = tc["function"]["arguments"]
            try:
                parsed_args = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                parsed_args = {}

            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": parsed_args,
                }
            )

        # Usage 변환
        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )

        return LLMResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            stop_reason=stop_reason,
            content=content_blocks,
            usage=usage,
        )

    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
