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

        Content is wrapped in a text content block list.
        """
        return [
            {
                'role': msg.role,
                'content': [
                    {'type': 'text', 'text': msg.content}
                ],
            }
            for msg in messages
        ]

    def _reconstruct_openai(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to OpenAI message format.

        Content is a plain string.
        """
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in messages
        ]

    def _reconstruct_gemini(
        self,
        messages: list[NormalizedMessage],
    ) -> list[dict[str, Any]]:
        """Reconstruct to Gemini message format.

        Uses parts list. Role 'assistant' mapped to 'model',
        'system' mapped to 'user'.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.role
            if role == 'assistant':
                role = 'model'
            elif role == 'system':
                role = 'user'

            result.append({
                'role': role,
                'parts': [{'text': msg.content}],
            })
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
