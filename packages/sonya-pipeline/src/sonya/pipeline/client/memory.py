"""sonya.pipeline.client.memory — DefaultMemoryPipeline implementation."""

from __future__ import annotations

import json as _json
from typing import Any

from sonya.core.schemas.memory import NormalizedMessage


class DefaultMemoryPipeline:
    """Default MemoryPipeline protocol implementation.

    Normalizes provider-native message histories to
    NormalizedMessage and reconstructs them back.
    Optionally persists sessions via a MemoryStore.

    Supports text content, tool_calls, and tool_results
    for Anthropic, OpenAI, and Gemini providers.

    Args:
        store: Optional MemoryStore for session persistence.

    Example::

        from sonya.pipeline import DefaultMemoryPipeline

        pipeline = DefaultMemoryPipeline()
        normalized = pipeline.normalize(history, 'anthropic')
        reconstructed = pipeline.reconstruct(normalized, 'openai')
    """

    def __init__(
        self,
        store: Any | None = None,
    ) -> None:
        self._store = store

    # ── normalize ───────────────────────────────────────────

    def normalize(
        self,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> list[NormalizedMessage]:
        """Normalize provider-native history to generic form.

        Args:
            history: Provider-native message list.
            source_provider: Provider name
                ('anthropic', 'openai', 'gemini').

        Returns:
            List of NormalizedMessage.
        """
        normalizer = {
            'anthropic': self._normalize_anthropic,
            'openai': self._normalize_openai,
            'gemini': self._normalize_gemini,
        }.get(source_provider, self._normalize_generic)

        return normalizer(history)

    def _normalize_anthropic(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize Anthropic-format messages.

        Anthropic content can be a string or a list of
        content blocks. Extracts text from type=='text' blocks,
        tool_calls from type=='tool_use' blocks, and
        tool_results from type=='tool_result' blocks.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            if isinstance(content, list):
                texts: list[str] = []
                for block in content:
                    btype = block.get('type')
                    if btype == 'text':
                        texts.append(block.get('text', ''))
                    elif btype == 'tool_use':
                        tool_calls.append({
                            'id': block.get('id', ''),
                            'name': block.get('name', ''),
                            'arguments': block.get('input', {}),
                        })
                    elif btype == 'tool_result':
                        tool_results.append({
                            'call_id': block.get('tool_use_id', ''),
                            'output': block.get('content', ''),
                            'name': block.get('name', ''),
                        })
                content = ''.join(texts)

            result.append(NormalizedMessage(
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_results=tool_results,
            ))
        return result

    def _normalize_openai(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize OpenAI-format messages.

        OpenAI content is a plain string. Tool calls appear
        in msg['tool_calls']. Tool results have role=='tool'.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            raw_content = msg.get('content') or ''
            content = str(raw_content) if raw_content else ''
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            if role == 'tool':
                # OpenAI tool result is a standalone message
                tool_results.append({
                    'call_id': msg.get('tool_call_id', ''),
                    'output': content,
                    'name': msg.get('name', ''),
                })
            else:
                raw_tcs = msg.get('tool_calls') or []
                for tc in raw_tcs:
                    func = tc.get('function', {})
                    args = func.get('arguments', {})
                    if isinstance(args, str):
                        try:
                            args = _json.loads(args)
                        except (_json.JSONDecodeError, ValueError):
                            args = {}
                    tool_calls.append({
                        'id': tc.get('id', ''),
                        'name': func.get('name', ''),
                        'arguments': args,
                    })

            result.append(NormalizedMessage(
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_results=tool_results,
            ))
        return result

    def _normalize_gemini(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize Gemini-format messages.

        Gemini uses 'parts' list with 'text', 'function_call',
        or 'function_response' fields. Role 'model' is mapped
        to 'assistant'. Synthetic IDs are assigned to tool calls
        since Gemini has no native call IDs.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            if role == 'model':
                role = 'assistant'

            parts = msg.get('parts', [])
            texts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            for i, part in enumerate(parts):
                if 'text' in part:
                    texts.append(part.get('text', ''))
                elif 'function_call' in part:
                    fc = part['function_call']
                    tool_calls.append({
                        'id': f'gemini_call_{i}',
                        'name': fc.get('name', ''),
                        'arguments': dict(fc.get('args', {})),
                    })
                elif 'function_response' in part:
                    fr = part['function_response']
                    response = fr.get('response', {})
                    tool_results.append({
                        'call_id': f'gemini_call_{i}',
                        'name': fr.get('name', ''),
                        'output': response.get('result', ''),
                    })

            result.append(NormalizedMessage(
                role=role,
                content=''.join(texts),
                tool_calls=tool_calls,
                tool_results=tool_results,
            ))
        return result

    def _normalize_generic(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Fallback normalizer for unknown providers.

        Expects standard role + content string format.
        """
        return [
            NormalizedMessage(
                role=msg.get('role', 'user'),
                content=str(msg.get('content', '')),
            )
            for msg in history
        ]

    # ── reconstruct ─────────────────────────────────────────

    def reconstruct(
        self,
        messages: list[NormalizedMessage],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        """Reconstruct normalized messages to provider-native form.

        Args:
            messages: List of NormalizedMessage.
            target_provider: Target provider name
                ('anthropic', 'openai', 'gemini').

        Returns:
            Provider-native message list.
        """
        reconstructor = {
            'anthropic': self._reconstruct_anthropic,
            'openai': self._reconstruct_openai,
            'gemini': self._reconstruct_gemini,
        }.get(target_provider, self._reconstruct_generic)

        return reconstructor(messages)

    def _reconstruct_anthropic(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to Anthropic message format.

        Text content is wrapped in a text content block.
        tool_calls become tool_use blocks.
        tool_results become tool_result blocks in user messages.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            content_blocks: list[dict[str, Any]] = []

            if msg.content:
                content_blocks.append(
                    {'type': 'text', 'text': msg.content}
                )

            for tc in msg.tool_calls:
                content_blocks.append({
                    'type': 'tool_use',
                    'id': tc.get('id', ''),
                    'name': tc.get('name', ''),
                    'input': tc.get('arguments', {}),
                })

            for tr in msg.tool_results:
                content_blocks.append({
                    'type': 'tool_result',
                    'tool_use_id': tr.get('call_id', ''),
                    'content': tr.get('output', ''),
                })

            # If no blocks at all, use empty text block
            if not content_blocks:
                content_blocks.append(
                    {'type': 'text', 'text': ''}
                )

            result.append({
                'role': msg.role,
                'content': content_blocks,
            })
        return result

    def _reconstruct_openai(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to OpenAI message format.

        tool_calls are added to assistant messages.
        tool_results become standalone role='tool' messages.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            # Tool result messages
            if msg.tool_results:
                for tr in msg.tool_results:
                    result.append({
                        'role': 'tool',
                        'tool_call_id': tr.get('call_id', ''),
                        'content': tr.get('output', ''),
                    })
                continue

            out: dict[str, Any] = {
                'role': msg.role,
                'content': msg.content,
            }
            if msg.tool_calls:
                out['tool_calls'] = [
                    {
                        'id': tc.get('id', ''),
                        'type': 'function',
                        'function': {
                            'name': tc.get('name', ''),
                            'arguments': _json.dumps(
                                tc.get('arguments', {})
                            ),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(out)
        return result

    def _reconstruct_gemini(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to Gemini message format.

        Uses parts list. Role 'assistant' mapped to 'model',
        'system' mapped to 'user'.
        function_call and function_response parts added for
        tool_calls and tool_results respectively.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.role
            if role == 'assistant':
                role = 'model'
            elif role == 'system':
                role = 'user'

            parts: list[dict[str, Any]] = []

            if msg.content:
                parts.append({'text': msg.content})

            for tc in msg.tool_calls:
                parts.append({
                    'function_call': {
                        'name': tc.get('name', ''),
                        'args': tc.get('arguments', {}),
                    }
                })

            for tr in msg.tool_results:
                parts.append({
                    'function_response': {
                        'name': tr.get('name', ''),
                        'response': {
                            'result': tr.get('output', ''),
                        },
                    }
                })

            if not parts:
                parts.append({'text': ''})

            result.append({'role': role, 'parts': parts})
        return result

    def _reconstruct_generic(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Fallback reconstructor for unknown providers."""
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in messages
        ]

    # ── session convenience methods ─────────────────────────────────

    def save_session(
        self,
        session_id: str,
        history: list[dict[str, Any]],
        source_provider: str,
    ) -> None:
        """Normalize history and save to store.

        Args:
            session_id: Unique session identifier.
            history: Provider-native message list.
            source_provider: Provider name of the history.

        Raises:
            ValueError: If no store is configured.
        """
        if self._store is None:
            raise ValueError('No store configured')
        normalized = self.normalize(history, source_provider)
        self._store.save(session_id, normalized)

    def load_session(
        self,
        session_id: str,
        target_provider: str,
        last_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load from store and reconstruct for target provider.

        Args:
            session_id: Unique session identifier.
            target_provider: Provider name to reconstruct for.
            last_n: If set, load only the last N messages.

        Returns:
            Provider-native message list.

        Raises:
            ValueError: If no store is configured.
        """
        if self._store is None:
            raise ValueError('No store configured')
        normalized = self._store.load(session_id, last_n)
        return self.reconstruct(normalized, target_provider)
