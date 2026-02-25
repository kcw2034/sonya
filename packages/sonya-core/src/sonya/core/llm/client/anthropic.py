"""
Anthropic API 클라이언트
- httpx.AsyncClient 기반 (anthropic SDK 미사용, 의존성 최소화)
- BaseLLMClient 구현체
- async context manager 지원
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator

import httpx

from ..base import BaseLLMClient
from ..models import (
    LLMResponse,
    LLMStreamChunk,
    StopReason,
    TextBlock,
    ToolUseBlock,
    Usage,
)

logger = logging.getLogger(__name__)

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
        max_retries: int = 3,
    ):
        resolved_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "api_key가 필요합니다. 직접 전달하거나 ANTHROPIC_API_KEY 환경변수를 설정하세요."
            )
        self.api_key: str = resolved_api_key
        self.model = model
        self.max_tokens = max_tokens
        self.system = system
        self.max_retries = max_retries
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

    async def _chat_impl(
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

        logger.debug(
            f"[anthropic] chat request: model={self.model}, "
            f"messages={len(messages)}"
        )

        response = await http.post(ANTHROPIC_API_URL, json=body)
        response.raise_for_status()

        result = LLMResponse.from_api_response(response.json())
        logger.debug(
            f"[anthropic] response: stop_reason={result.stop_reason.value}, "
            f"usage=({result.usage.input_tokens}in/{result.usage.output_tokens}out)"
        )
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        http = await self._get_http()

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "stream": True,
        }
        if self.system:
            body["system"] = self.system
        if tools:
            body["tools"] = tools

        logger.debug(
            f"[anthropic] stream request: model={self.model}, "
            f"messages={len(messages)}"
        )

        message_id = ""
        model = self.model
        stop_reason = "end_turn"
        input_tokens = 0
        output_tokens = 0
        content_blocks_by_index: dict[int, dict] = {}
        tool_input_json_by_index: dict[int, str] = {}

        async with http.stream("POST", ANTHROPIC_API_URL, json=body) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                raw = line.removeprefix("data:").strip()
                if not raw:
                    continue

                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type")

                if event_type == "message_start":
                    message = event.get("message", {})
                    message_id = message.get("id", message_id)
                    model = message.get("model", model)
                    usage = message.get("usage", {})
                    input_tokens = usage.get("input_tokens", input_tokens)
                    continue

                if event_type == "content_block_delta":
                    block_index = event.get("index")
                    if not isinstance(block_index, int):
                        continue

                    delta = event.get("delta", {})
                    delta_type = delta.get("type")

                    text = delta.get("text") if delta_type == "text_delta" else None
                    if text:
                        block = content_blocks_by_index.get(block_index)
                        if not block:
                            block = {"type": "text", "text": ""}
                            content_blocks_by_index[block_index] = block
                        if block.get("type") == "text":
                            block["text"] = f"{block.get('text', '')}{text}"
                        yield LLMStreamChunk(delta_text=text)

                    partial_json = (
                        delta.get("partial_json")
                        if delta_type == "input_json_delta"
                        else None
                    )
                    if partial_json:
                        prev = tool_input_json_by_index.get(block_index, "")
                        tool_input_json_by_index[block_index] = f"{prev}{partial_json}"
                    continue

                if event_type == "content_block_start":
                    block_index = event.get("index")
                    block = event.get("content_block", {})
                    if not isinstance(block_index, int) or not isinstance(block, dict):
                        continue
                    block_type = block.get("type")
                    if block_type == "text":
                        content_blocks_by_index[block_index] = {
                            "type": "text",
                            "text": block.get("text", ""),
                        }
                    elif block_type == "tool_use":
                        content_blocks_by_index[block_index] = {
                            "type": "tool_use",
                            "id": block.get("id", ""),
                            "name": block.get("name", ""),
                            "input": block.get("input", {}),
                        }
                    continue

                if event_type == "content_block_stop":
                    block_index = event.get("index")
                    if not isinstance(block_index, int):
                        continue
                    block = content_blocks_by_index.get(block_index)
                    if not block or block.get("type") != "tool_use":
                        continue

                    partial_input = tool_input_json_by_index.get(block_index)
                    if not partial_input:
                        continue

                    try:
                        block["input"] = json.loads(partial_input)
                    except json.JSONDecodeError:
                        block["input"] = {}
                    continue

                if event_type == "message_delta":
                    delta = event.get("delta", {})
                    stop_reason = delta.get("stop_reason") or stop_reason
                    usage = event.get("usage", {})
                    output_tokens = usage.get("output_tokens", output_tokens)
                    continue

                if event_type == "message_stop":
                    break

        try:
            parsed_stop_reason = StopReason(stop_reason)
        except ValueError:
            parsed_stop_reason = StopReason.END_TURN

        content_blocks = []
        for index in sorted(content_blocks_by_index.keys()):
            block = content_blocks_by_index[index]
            if block.get("type") == "text":
                content_blocks.append(TextBlock(text=str(block.get("text", ""))))
            elif block.get("type") == "tool_use":
                content_blocks.append(
                    ToolUseBlock(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        input=block.get("input", {}),
                    )
                )

        final_response = LLMResponse(
            id=message_id,
            model=model,
            stop_reason=parsed_stop_reason,
            content=content_blocks,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )
        logger.debug(
            f"[anthropic] stream done: stop_reason={parsed_stop_reason.value}, "
            f"usage=({input_tokens}in/{output_tokens}out)"
        )
        yield LLMStreamChunk(response=final_response)

    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def __aenter__(self) -> AnthropicClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
