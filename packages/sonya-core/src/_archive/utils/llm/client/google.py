from __future__ import annotations

import json
import uuid

from ....llm.models import LLMResponse, StopReason, Usage


def _convert_messages(messages: list[dict], call_id_map: dict[str, str]) -> list[dict]:
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                call_id_map[block["id"]] = block["name"]

    gemini_messages = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        gemini_role = "model" if role == "assistant" else "user"

        if isinstance(content, str):
            gemini_messages.append({"role": gemini_role, "parts": [{"text": content}]})
            continue

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
                            }
                        }
                    )
                elif block.get("type") == "tool_result":
                    tool_use_id = block["tool_use_id"]
                    fn_name = call_id_map.get(tool_use_id, "unknown")
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
                            }
                        }
                    )

            if parts:
                gemini_messages.append({"role": gemini_role, "parts": parts})
            continue

        gemini_messages.append({"role": gemini_role, "parts": [{"text": str(content)}]})

    return gemini_messages


def _convert_tools(tools: list[dict]) -> list[dict]:
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


def _parse_response(
    data: dict,
    default_model: str,
    call_id_map: dict[str, str],
) -> LLMResponse:
    candidate = data["candidates"][0]
    parts = candidate.get("content", {}).get("parts", [])
    finish_reason = candidate.get("finishReason", "STOP")

    content_blocks = []
    has_function_call = False

    for part in parts:
        if "text" in part:
            content_blocks.append({"type": "text", "text": part["text"]})
        elif "functionCall" in part:
            has_function_call = True
            fc = part["functionCall"]
            call_id = f"gemini_{uuid.uuid4().hex[:12]}"
            call_id_map[call_id] = fc["name"]
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": call_id,
                    "name": fc["name"],
                    "input": fc.get("args", {}),
                }
            )

    if has_function_call:
        stop_reason = StopReason.TOOL_USE
    elif finish_reason == "MAX_TOKENS":
        stop_reason = StopReason.MAX_TOKENS
    else:
        stop_reason = StopReason.END_TURN

    usage_data = data.get("usageMetadata", {})
    usage = Usage(
        input_tokens=usage_data.get("promptTokenCount", 0),
        output_tokens=usage_data.get("candidatesTokenCount", 0),
    )

    return LLMResponse(
        id=data.get("id", f"gemini_{uuid.uuid4().hex[:8]}"),
        model=data.get("modelVersion", default_model),
        stop_reason=stop_reason,
        content=content_blocks,
        usage=usage,
    )
