from __future__ import annotations

import json

from ....llm.models import LLMResponse, StopReason, Usage


def _convert_messages(messages: list[dict]) -> list[dict]:
    openai_messages = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
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

        openai_messages.append({"role": role, "content": str(content)})

    return openai_messages


def _convert_tools(tools: list[dict]) -> list[dict]:
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


def _parse_response(data: dict) -> LLMResponse:
    choice = data["choices"][0]
    message = choice["message"]
    finish_reason = choice["finish_reason"]

    reason_map = {
        "stop": StopReason.END_TURN,
        "tool_calls": StopReason.TOOL_USE,
        "length": StopReason.MAX_TOKENS,
    }
    stop_reason = reason_map.get(finish_reason, StopReason.END_TURN)

    content_blocks = []
    if message.get("content"):
        content_blocks.append(
            {
                "type": "text",
                "text": message["content"],
            }
        )

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
