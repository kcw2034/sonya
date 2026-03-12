"""ContextRouter — selects cache or memory pipeline path on handoff."""

from __future__ import annotations

import logging
from typing import Any

from sonya.core.models.agent import Agent
from sonya.core.cache.base import BaseCache
from sonya.core.schemas.memory import MemoryPipeline
from sonya.core.utils.tool_context import ToolContext

_log = logging.getLogger('sonya.router')

_PROVIDER_MAP: dict[str, str] = {
    'AnthropicClient': 'anthropic',
    'OpenAIClient': 'openai',
    'GeminiClient': 'gemini',
}


class ContextRouter:
    """Routes handoff context between agents.

    Selects between:
    - **Cache path** (same provider): pass native history directly.
    - **Memory pipeline** (cross provider): normalize then reconstruct.
    - **Fallback**: filter to user/system messages only.

    Args:
        cache_registry: Provider-name to BaseCache mapping.
        pipeline: Optional MemoryPipeline for cross-provider conversion.
    """

    def __init__(
        self,
        cache_registry: dict[str, BaseCache] | None = None,
        pipeline: MemoryPipeline | None = None,
    ) -> None:
        self._cache_registry = cache_registry or {}
        self._pipeline = pipeline

    def _detect_provider(self, agent: Agent) -> str:
        """Detect the LLM provider from the agent's client class name.

        Args:
            agent: The agent to inspect.

        Returns:
            Provider string ('anthropic', 'openai', 'gemini', 'unknown').
        """
        class_name = type(agent.client).__name__
        return _PROVIDER_MAP.get(class_name, 'unknown')

    async def route(
        self,
        source: Agent,
        target: Agent,
        history: list[dict[str, Any]],
        context: ToolContext,
    ) -> list[dict[str, Any]]:
        """Route context from source agent to target agent.

        Args:
            source: The agent handing off.
            target: The agent receiving the handoff.
            history: Conversation history from the source agent.
            context: Shared ToolContext for recording metadata.

        Returns:
            History list suitable for the target agent.
        """
        src_provider = self._detect_provider(source)
        tgt_provider = self._detect_provider(target)

        context.set('source_provider', src_provider)
        context.set('target_provider', tgt_provider)

        if src_provider == tgt_provider:
            return self._cache_path(
                history, src_provider, context,
            )

        return self._memory_path(
            history, src_provider, tgt_provider, context,
        )

    def _cache_path(
        self,
        history: list[dict[str, Any]],
        provider: str,
        context: ToolContext,
    ) -> list[dict[str, Any]]:
        """Same-provider path: pass history directly.

        Args:
            history: Native message history.
            provider: The shared provider name.
            context: ToolContext for recording metadata.

        Returns:
            The history unchanged.
        """
        context.set('routing_path', 'cache')
        _log.debug(
            'Cache path: %s (same provider)', provider,
        )
        return history

    def _memory_path(
        self,
        history: list[dict[str, Any]],
        src_provider: str,
        tgt_provider: str,
        context: ToolContext,
    ) -> list[dict[str, Any]]:
        """Cross-provider path: normalize then reconstruct.

        Falls back to user/system filter if no pipeline
        is configured or if conversion fails.

        Args:
            history: Source provider's native message history.
            src_provider: Source provider name.
            tgt_provider: Target provider name.
            context: ToolContext for recording metadata.

        Returns:
            Converted history or fallback filtered history.
        """
        context.set('routing_path', 'memory')

        if self._pipeline is None:
            _log.warning(
                'No pipeline configured; '
                'falling back to user/system filter',
            )
            context.set('routing_path', 'fallback')
            return self._fallback(history)

        # Intentional broad catch: MemoryPipeline is an external
        # protocol whose implementations may raise any exception.
        # A failed pipeline conversion is non-fatal — we fall back
        # to the safe user/system filter and log the full traceback
        # for debugging.
        try:
            normalized = self._pipeline.normalize(
                history, src_provider,
            )
            result = self._pipeline.reconstruct(
                normalized, tgt_provider,
            )
            _log.debug(
                'Memory path: %s -> %s (%d messages)',
                src_provider, tgt_provider, len(result),
            )
            return result
        except Exception:
            _log.warning(
                'Pipeline conversion failed; '
                'falling back to user/system filter',
                exc_info=True,
            )
            context.set('routing_path', 'fallback')
            return self._fallback(history)

    @staticmethod
    def _fallback(
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter history to user and system messages only.

        Args:
            history: Full message history.

        Returns:
            Filtered list with only user/system roles.
        """
        return [
            m for m in history
            if m.get('role') in ('user', 'system')
        ]
