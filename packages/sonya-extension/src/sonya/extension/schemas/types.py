"""Shared type definitions and message format converters."""

from __future__ import annotations

from typing import Any


def _check_langchain() -> None:
    """Verify langchain-core is installed.

    Raises:
        ImportError: If langchain-core is not available.
    """
    try:
        import langchain_core  # noqa: F401
    except ImportError:
        raise ImportError(
            "langchain-core is required for LangChain "
            "integration. Install it with: "
            "pip install sonya-extension[langchain]"
        )


def sonya_to_langchain_messages(
    messages: list[dict[str, Any]],
) -> list[Any]:
    """Convert sonya message dicts to LangChain BaseMessage list.

    Args:
        messages: List of sonya-format message dicts with
            'role' and 'content' keys.

    Returns:
        List of LangChain BaseMessage instances.
    """
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    result = []
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')

        if role == 'system':
            result.append(SystemMessage(content=content))
        elif role == 'user':
            result.append(HumanMessage(content=content))
        elif role == 'assistant':
            tool_calls = _extract_tool_calls(msg)
            if tool_calls:
                result.append(AIMessage(
                    content=content or '',
                    tool_calls=tool_calls,
                ))
            else:
                result.append(AIMessage(content=content))
        elif role == 'tool':
            result.append(ToolMessage(
                content=content,
                tool_call_id=msg.get('tool_call_id', ''),
            ))

    return result


def langchain_to_sonya_messages(
    messages: list[Any],
) -> list[dict[str, Any]]:
    """Convert LangChain BaseMessage list to sonya message dicts.

    Args:
        messages: List of LangChain BaseMessage instances.

    Returns:
        List of sonya-format message dicts.
    """
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    result: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({
                'role': 'system',
                'content': msg.content,
            })
        elif isinstance(msg, HumanMessage):
            result.append({
                'role': 'user',
                'content': msg.content,
            })
        elif isinstance(msg, AIMessage):
            entry: dict[str, Any] = {
                'role': 'assistant',
                'content': msg.content or '',
            }
            if msg.tool_calls:
                entry['tool_calls'] = [
                    {
                        'id': tc['id'],
                        'type': 'function',
                        'function': {
                            'name': tc['name'],
                            'arguments': tc['args'],
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(entry)
        elif isinstance(msg, ToolMessage):
            result.append({
                'role': 'tool',
                'tool_call_id': msg.tool_call_id,
                'content': msg.content,
            })

    return result


def _extract_tool_calls(
    msg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract LangChain-format tool calls from a sonya message.

    Args:
        msg: A sonya assistant message dict.

    Returns:
        List of tool call dicts with name, args, id keys.
    """
    raw_calls = msg.get('tool_calls', [])
    if not raw_calls:
        return []

    calls = []
    for tc in raw_calls:
        func = tc.get('function', {})
        calls.append({
            'name': func.get('name', ''),
            'args': func.get('arguments', {}),
            'id': tc.get('id', ''),
            'type': 'tool_call',
        })
    return calls
