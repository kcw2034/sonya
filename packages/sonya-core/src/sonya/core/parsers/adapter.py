"""Response adapters — parse native LLM responses into a common shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ParsedToolCall:
    """A single tool call extracted from an LLM response.

    Args:
        id: Provider-assigned call identifier.
        name: Tool name the LLM wants to invoke.
        arguments: Parsed argument dict.
    """

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ParsedResponse:
    """Normalised view of an LLM response.

    Args:
        text: Concatenated text content (may be empty).
        tool_calls: List of tool calls requested by the LLM.
        stop_reason: Why the LLM stopped (``'end'``, ``'tool_use'``).
        raw: The original native response object.
    """

    text: str
    tool_calls: list[ParsedToolCall]
    stop_reason: str
    raw: Any = None


class ResponseAdapter(Protocol):
    """Protocol for parsing native LLM responses."""

    def parse(self, response: Any) -> ParsedResponse:
        """Parse a native response into :class:`ParsedResponse`."""
        ...

    def format_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert messages to provider-specific format.

        Called by the orchestration layer before passing messages
        to the client. Providers that use a non-OpenAI message
        format override this to perform conversion.

        Args:
            messages: Message list (may be mixed format).

        Returns:
            Provider-formatted message list.
        """
        ...

    def format_generate_kwargs(
        self,
        instructions: str,
        tool_schemas: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build provider-specific kwargs for generate().

        Args:
            instructions: System prompt for the agent.
            tool_schemas: Tool schemas in the provider's format, or None.

        Returns:
            Dict of kwargs to pass to ``client.generate()``.
        """
        ...

    def format_assistant_message(
        self, response: Any
    ) -> dict[str, Any]:
        """Format the native response as a history message."""
        ...

    def format_tool_results_message(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Format tool results as a history message.

        Anthropic returns a single dict (user message with
        tool_result blocks). OpenAI returns a list of dicts
        (one tool-role message per result).
        """
        ...


# ---- Anthropic Adapter ----

class AnthropicAdapter:
    """Adapter for Anthropic message responses."""

    def format_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Pass through — Anthropic uses the canonical format."""
        return messages

    def parse(self, response: Any) -> ParsedResponse:
        """Parse Anthropic response.

        Extracts text from ``content[].type == 'text'`` and tool calls
        from ``content[].type == 'tool_use'``.
        """
        text_parts: list[str] = []
        tool_calls: list[ParsedToolCall] = []

        for block in getattr(response, 'content', []):
            if getattr(block, 'type', None) == 'text':
                text_parts.append(block.text)
            elif getattr(block, 'type', None) == 'tool_use':
                tool_calls.append(ParsedToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input or {},
                ))

        stop = getattr(response, 'stop_reason', 'end')
        stop_reason = 'tool_use' if stop == 'tool_use' else 'end'

        return ParsedResponse(
            text='\n'.join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response,
        )

    def format_generate_kwargs(
        self,
        instructions: str,
        tool_schemas: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build Anthropic-specific generate kwargs."""
        kwargs: dict[str, Any] = {}
        if instructions:
            kwargs['system'] = instructions
        if tool_schemas:
            kwargs['tools'] = tool_schemas
        return kwargs

    def format_assistant_message(
        self, response: Any
    ) -> dict[str, Any]:
        """Re-serialise Anthropic response content as assistant message."""
        content = []
        for block in getattr(response, 'content', []):
            if getattr(block, 'type', None) == 'text':
                content.append(
                    {'type': 'text', 'text': block.text}
                )
            elif getattr(block, 'type', None) == 'tool_use':
                content.append({
                    'type': 'tool_use',
                    'id': block.id,
                    'name': block.name,
                    'input': block.input or {},
                })
        return {'role': 'assistant', 'content': content}

    def format_tool_results_message(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Format tool results for Anthropic's ``tool_result`` blocks."""
        content = []
        for r in results:
            content.append({
                'type': 'tool_result',
                'tool_use_id': r['call_id'],
                'content': r.get(
                    'output', r.get('error', '')
                ),
                'is_error': not r.get('success', True),
            })
        return {'role': 'user', 'content': content}


# ---- OpenAI Adapter ----

class OpenAIAdapter:
    """Adapter for OpenAI chat completion responses."""

    def format_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Pass through — OpenAI uses the canonical format."""
        return messages

    def parse(self, response: Any) -> ParsedResponse:
        """Parse OpenAI response.

        Reads ``choices[0].message.tool_calls`` and
        ``choices[0].message.content``.
        """
        import json as _json

        message = response.choices[0].message
        text = message.content or ''
        tool_calls: list[ParsedToolCall] = []

        for tc in message.tool_calls or []:
            args = tc.function.arguments
            if isinstance(args, str):
                args = _json.loads(args)
            tool_calls.append(ParsedToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))

        finish = response.choices[0].finish_reason
        stop_reason = (
            'tool_use' if finish == 'tool_calls' else 'end'
        )

        return ParsedResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response,
        )

    def format_generate_kwargs(
        self,
        instructions: str,
        tool_schemas: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build OpenAI-specific generate kwargs.

        Stores instructions under ``_system_message`` for
        the runtime to prepend as a system message.
        """
        kwargs: dict[str, Any] = {}
        if instructions:
            kwargs['_system_message'] = instructions
        if tool_schemas:
            kwargs['tools'] = tool_schemas
        return kwargs

    def format_assistant_message(
        self, response: Any
    ) -> dict[str, Any]:
        """Serialise OpenAI message back into the history format."""
        import json as _json

        message = response.choices[0].message
        msg: dict[str, Any] = {
            'role': 'assistant',
            'content': message.content or '',
        }
        if message.tool_calls:
            msg['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.function.name,
                        'arguments': (
                            tc.function.arguments
                            if isinstance(
                                tc.function.arguments, str
                            )
                            else _json.dumps(
                                tc.function.arguments
                            )
                        ),
                    },
                }
                for tc in message.tool_calls
            ]
        return msg

    def format_tool_results_message(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format tool results as separate ``tool`` role messages."""
        messages = []
        for r in results:
            messages.append({
                'role': 'tool',
                'tool_call_id': r['call_id'],
                'content': r.get(
                    'output', r.get('error', '')
                ),
            })
        return messages


# ---- Gemini Adapter ----

class GeminiAdapter:
    """Adapter for Google Gemini generate_content responses."""

    _ROLE_MAP: dict[str, str] = {
        'assistant': 'model',
        'system': 'user',
    }

    def format_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert OpenAI-style messages to Gemini format.

        Messages already in Gemini format (containing ``parts``)
        pass through unchanged. Messages with a ``content`` key
        are converted to ``{'role': ..., 'parts': [...]}``.

        Args:
            messages: Mixed-format message list.

        Returns:
            List of Gemini-formatted message dicts.
        """
        converted: list[dict[str, Any]] = []
        for msg in messages:
            if 'parts' in msg:
                converted.append(msg)
                continue
            role = self._ROLE_MAP.get(
                msg.get('role', 'user'),
                msg.get('role', 'user'),
            )
            content = msg.get('content', '')
            if isinstance(content, str):
                parts = (
                    [{'text': content}] if content else []
                )
            elif isinstance(content, list):
                parts = [
                    {'text': str(c)} for c in content
                ]
            else:
                parts = [{'text': str(content)}]
            converted.append(
                {'role': role, 'parts': parts}
            )
        return converted

    def parse(self, response: Any) -> ParsedResponse:
        """Parse Gemini response.

        Reads ``candidates[0].content.parts`` for text and
        function_call entries.
        """
        text_parts: list[str] = []
        tool_calls: list[ParsedToolCall] = []

        candidates = (
            getattr(response, 'candidates', []) or []
        )
        if candidates:
            parts = getattr(
                candidates[0].content, 'parts', []
            ) or []
            for i, part in enumerate(parts):
                if getattr(part, 'text', None):
                    text_parts.append(part.text)
                fc = getattr(part, 'function_call', None)
                if fc is not None:
                    tool_calls.append(ParsedToolCall(
                        id=f'gemini_call_{i}',
                        name=fc.name,
                        arguments=(
                            dict(fc.args) if fc.args else {}
                        ),
                    ))

        stop_reason = 'tool_use' if tool_calls else 'end'
        return ParsedResponse(
            text='\n'.join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response,
        )

    def format_generate_kwargs(
        self,
        instructions: str,
        tool_schemas: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build Gemini-specific generate kwargs.

        Wraps tool schemas in ``function_declarations`` and maps
        system prompt to ``system_instruction``.
        """
        kwargs: dict[str, Any] = {}
        if instructions:
            kwargs['system_instruction'] = instructions
        if tool_schemas:
            # Gemini expects Tool(functionDeclarations=[...])
            kwargs['tools'] = [
                {'function_declarations': tool_schemas}
            ]
        return kwargs

    def format_assistant_message(
        self, response: Any
    ) -> dict[str, Any]:
        """Format Gemini response as a model message."""
        parts: list[dict[str, Any]] = []
        candidates = (
            getattr(response, 'candidates', []) or []
        )
        if candidates:
            for part in getattr(
                candidates[0].content, 'parts', []
            ) or []:
                if getattr(part, 'text', None):
                    parts.append({'text': part.text})
                fc = getattr(part, 'function_call', None)
                if fc is not None:
                    parts.append({
                        'function_call': {
                            'name': fc.name,
                            'args': (
                                dict(fc.args)
                                if fc.args else {}
                            ),
                        }
                    })
        return {'role': 'model', 'parts': parts}

    def format_tool_results_message(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Format tool results as Gemini function_response parts."""
        parts = []
        for r in results:
            parts.append({
                'function_response': {
                    'name': r['name'],
                    'response': {
                        'result': r.get(
                            'output', r.get('error', '')
                        ),
                    },
                }
            })
        return {'role': 'user', 'parts': parts}


# ---- Auto-detect adapter ----

_ADAPTER_MAP: dict[str, type] = {
    'AnthropicClient': AnthropicAdapter,
    'OpenAIClient': OpenAIAdapter,
    'GeminiClient': GeminiAdapter,
}


def register_adapter(
    client_class_name: str,
    adapter_cls: type,
) -> None:
    """Register a custom adapter for a client class.

    Args:
        client_class_name: The class name of the client.
        adapter_cls: The adapter class to use.
    """
    _ADAPTER_MAP[client_class_name] = adapter_cls


def _get_adapter(client: Any) -> ResponseAdapter:
    """Return the appropriate adapter for *client*.

    Detects client type by class name to avoid importing SDK packages.

    Raises:
        ValueError: If the client type is not recognised.
    """
    cls_name = type(client).__name__
    adapter_cls = _ADAPTER_MAP.get(cls_name)
    if adapter_cls is None:
        raise ValueError(
            f"No adapter found for client type '{cls_name}'. "
            f"Supported: {list(_ADAPTER_MAP.keys())}"
        )
    return adapter_cls()
