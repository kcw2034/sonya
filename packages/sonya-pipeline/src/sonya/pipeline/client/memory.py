"""sonya.pipeline.client.memory — DefaultMemoryPipeline implementation."""

from __future__ import annotations

from typing import Any

from sonya.core.schemas.memory import NormalizedMessage


class DefaultMemoryPipeline:
    """Default MemoryPipeline protocol implementation.

    Normalizes provider-native message histories to
    NormalizedMessage and reconstructs them back.
    Optionally persists sessions via a MemoryStore.

    First iteration supports text content only.
    tool_calls and tool_results are not yet handled.

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
        content blocks. Extracts text from type=='text' blocks.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if isinstance(content, list):
                texts = [
                    block.get('text', '')
                    for block in content
                    if block.get('type') == 'text'
                ]
                content = ''.join(texts)

            result.append(
                NormalizedMessage(role=role, content=content)
            )
        return result

    def _normalize_openai(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize OpenAI-format messages.

        OpenAI content is a plain string.
        """
        return [
            NormalizedMessage(
                role=msg.get('role', 'user'),
                content=msg.get('content', ''),
            )
            for msg in history
        ]

    def _normalize_gemini(
        self,
        history: list[dict[str, Any]],
    ) -> list[NormalizedMessage]:
        """Normalize Gemini-format messages.

        Gemini uses 'parts' list with 'text' fields.
        Role 'model' is mapped to 'assistant'.
        """
        result: list[NormalizedMessage] = []
        for msg in history:
            role = msg.get('role', 'user')
            if role == 'model':
                role = 'assistant'

            parts = msg.get('parts', [])
            texts = [
                p.get('text', '')
                for p in parts
                if 'text' in p
            ]
            content = ''.join(texts)

            result.append(
                NormalizedMessage(role=role, content=content)
            )
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
