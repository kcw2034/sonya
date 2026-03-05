"""
OpenAI API 클라이언트
- httpx.AsyncClient 기반 (openai SDK 미사용, 의존성 최소화)
- Chat Completions API + function calling 지원
- BaseLLMClient 구현체
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..base import BaseLLMClient
from ..error import StructuredOutputError
from ..schema import _schema_to_json_schema
from ..models import (
    LLMResponse,
    LLMStreamChunk,
    StopReason,
    TextBlock,
    ToolUseBlock,
    Usage,
)
from ...utils.llm.client.openai import (
    _convert_messages,
    _convert_tools,
    _parse_response,
)

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

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
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "api_key가 필요합니다. 직접 전달하거나 OPENAI_API_KEY 환경변수를 설정하세요."
            )
        self.model = model
        self.max_tokens = max_tokens
        self.system = system
        self.max_retries = max_retries
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

    async def chat_structured(
        self,
        messages: list[dict],
        output_schema: type[T],
    ) -> T:
        """
        OpenAI 네이티브 Structured Output (response_format)

        response_format: {"type": "json_schema", "json_schema": {...}} 을 사용하여
        LLM 응답을 JSON Schema에 맞춰 강제한다. 별도 Tool 정의 없이 텍스트 응답 자체가
        스키마에 부합하는 JSON으로 반환된다.
        """
        http = await self._get_http()

        openai_messages = _convert_messages(messages)
        if self.system:
            openai_messages.insert(0, {"role": "system", "content": self.system})

        json_schema = _schema_to_json_schema(output_schema)

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": openai_messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__,
                    "schema": json_schema,
                    "strict": True,
                },
            },
        }

        logger.debug(
            f"[openai] structured output request: model={self.model}, "
            f"schema={output_schema.__name__}"
        )

        response = await http.post(OPENAI_API_URL, json=body)
        response.raise_for_status()

        data = response.json()
        choice = data["choices"][0]
        raw_content = choice.get("message", {}).get("content", "")

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            raise StructuredOutputError(
                schema_name=output_schema.__name__,
                raw_output=raw_content,
                message=f"JSON 파싱 실패: {e}",
            ) from e

        try:
            return output_schema.model_validate(parsed)
        except ValidationError as e:
            raise StructuredOutputError(
                schema_name=output_schema.__name__,
                raw_output=raw_content,
                message=str(e),
            ) from e

    async def _chat_impl(
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

        openai_messages = _convert_messages(messages)

        # system 메시지를 맨 앞에 삽입
        if self.system:
            openai_messages.insert(0, {"role": "system", "content": self.system})

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": openai_messages,
        }
        if tools:
            body["tools"] = _convert_tools(tools)

        logger.debug(
            f"[openai] chat request: model={self.model}, messages={len(messages)}"
        )

        response = await http.post(OPENAI_API_URL, json=body)
        response.raise_for_status()

        result = _parse_response(response.json())
        logger.debug(
            f"[openai] response: stop_reason={result.stop_reason.value}, "
            f"usage=({result.usage.input_tokens}in/{result.usage.output_tokens}out)"
        )
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        OpenAI Chat Completions 스트리밍 호출

        SSE 이벤트를 파싱하여 텍스트 delta를 실시간으로 yield하고,
        스트림 종료 시 전체 LLMResponse를 최종 청크로 yield한다.

        OpenAI 스트리밍 포맷:
            data: {"choices": [{"delta": {"content": "..."}, "finish_reason": null}]}
            data: {"choices": [{"delta": {"tool_calls": [...]}, "finish_reason": null}]}
            data: [DONE]
        """
        http = await self._get_http()

        openai_messages = _convert_messages(messages)
        if self.system:
            openai_messages.insert(0, {"role": "system", "content": self.system})

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = _convert_tools(tools)

        logger.debug(
            f"[openai] stream request: model={self.model}, messages={len(messages)}"
        )

        # 스트림 누적 상태
        response_id = ""
        model = self.model
        finish_reason = "stop"
        input_tokens = 0
        output_tokens = 0
        text_content = ""
        # tool_calls 누적: index → {id, name, arguments_chunks}
        tool_calls_by_index: dict[int, dict] = {}

        async with http.stream("POST", OPENAI_API_URL, json=body) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                raw = line.removeprefix("data:").strip()
                if raw == "[DONE]":
                    break
                if not raw:
                    continue

                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # usage 전용 청크 (stream_options.include_usage=True)
                usage_data = event.get("usage")
                if usage_data:
                    input_tokens = usage_data.get("prompt_tokens", input_tokens)
                    output_tokens = usage_data.get("completion_tokens", output_tokens)

                response_id = event.get("id", response_id)
                model = event.get("model", model)

                choices = event.get("choices")
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})

                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

                # 텍스트 delta
                text_delta = delta.get("content")
                if text_delta:
                    text_content += text_delta
                    yield LLMStreamChunk(delta_text=text_delta)

                # tool_calls delta 누적
                for tc_delta in delta.get("tool_calls", []):
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {
                            "id": tc_delta.get("id", ""),
                            "name": "",
                            "arguments": "",
                        }

                    entry = tool_calls_by_index[idx]
                    if tc_delta.get("id"):
                        entry["id"] = tc_delta["id"]
                    fn = tc_delta.get("function", {})
                    if fn.get("name"):
                        entry["name"] = fn["name"]
                    if fn.get("arguments"):
                        entry["arguments"] += fn["arguments"]

        # StopReason 매핑
        reason_map = {
            "stop": StopReason.END_TURN,
            "tool_calls": StopReason.TOOL_USE,
            "length": StopReason.MAX_TOKENS,
        }
        stop_reason = reason_map.get(finish_reason, StopReason.END_TURN)

        # 최종 content 블록 조립
        content_blocks = []
        if text_content:
            content_blocks.append(TextBlock(text=text_content))

        for idx in sorted(tool_calls_by_index.keys()):
            tc = tool_calls_by_index[idx]
            try:
                parsed_args = json.loads(tc["arguments"])
            except (json.JSONDecodeError, TypeError):
                parsed_args = {}
            content_blocks.append(
                ToolUseBlock(
                    id=tc["id"],
                    name=tc["name"],
                    input=parsed_args,
                )
            )

        final_response = LLMResponse(
            id=response_id,
            model=model,
            stop_reason=stop_reason,
            content=content_blocks,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        )
        logger.debug(
            f"[openai] stream done: stop_reason={stop_reason.value}, "
            f"usage=({input_tokens}in/{output_tokens}out)"
        )
        yield LLMStreamChunk(response=final_response)

    async def close(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
