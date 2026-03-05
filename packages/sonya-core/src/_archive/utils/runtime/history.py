from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...llm.models import Message, TextBlock, ToolUseBlock

if TYPE_CHECKING:
    from ...llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


def _estimate_tokens(
    messages: list[Message],
    chars_per_token: float,
    last_input_tokens: int | None,
) -> int:
    if last_input_tokens is not None:
        return last_input_tokens

    total_chars = 0
    for msg in messages:
        if isinstance(msg.content, str):
            total_chars += len(msg.content)
            continue

        for block in msg.content:
            if isinstance(block, TextBlock):
                total_chars += len(block.text)
            elif isinstance(block, ToolUseBlock):
                total_chars += len(str(block.input)) + len(block.name)
            else:
                total_chars += len(getattr(block, "content", ""))

    return int(total_chars / chars_per_token)


def _has_tool_use(message: Message) -> bool:
    if isinstance(message.content, str):
        return False
    return any(isinstance(b, ToolUseBlock) for b in message.content)


def _find_split_index(
    messages: list[Message],
    keep_recent: int,
    max_tokens: int | None,
    max_messages: int | None,
    estimate_tokens,
) -> int:
    n = len(messages)
    protect_count = keep_recent * 2
    max_split = max(0, n - protect_count)

    if max_split <= 0:
        return 0

    candidates: list[int] = []
    for i in range(1, max_split + 1):
        msg_at_i = messages[i]
        prev_msg = messages[i - 1]

        if msg_at_i.role != "user":
            continue

        if prev_msg.role == "assistant" and _has_tool_use(prev_msg):
            continue

        candidates.append(i)

    if not candidates:
        return 0

    if max_tokens is not None:
        for idx in reversed(candidates):
            remaining = messages[idx:]
            if estimate_tokens(remaining) <= max_tokens:
                return idx
        return candidates[-1]

    if max_messages is not None:
        for idx in reversed(candidates):
            if (n - idx) <= max_messages:
                return idx
        return candidates[-1]

    return 0


def _build_conversation_text(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        if isinstance(msg.content, str):
            lines.append(f"{msg.role}: {msg.content}")
            continue

        parts: list[str] = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                parts.append(f"[Tool: {block.name}({block.input})]")
            else:
                parts.append(f"[ToolResult: {getattr(block, 'content', '')}]")
        lines.append(f"{msg.role}: {''.join(parts)}")

    return "\n".join(lines)


async def _summarize_messages(
    client: BaseLLMClient | None,
    messages: list[Message],
    summary_output_schema: type,
) -> Message | None:
    if client is None:
        return None

    conversation_text = _build_conversation_text(messages)
    summary_messages = [
        {
            "role": "user",
            "content": (
                "다음 대화 내용을 간결하게 요약해주세요. "
                "핵심 정보와 맥락만 유지하세요.\n\n"
                f"{conversation_text}"
            ),
        }
    ]

    try:
        result = await client.chat_structured(
            messages=summary_messages,
            output_schema=summary_output_schema,
        )
        return Message(
            role="user",
            content=f"[이전 대화 요약] {getattr(result, 'summary', '')}",
        )
    except Exception as e:
        logger.warning(f"히스토리 요약 실패, 단순 드롭으로 폴백: {e}")
        return None
