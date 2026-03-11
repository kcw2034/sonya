"""BaseClient ABC — base for all provider clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from sonya.core.schemas.types import ClientConfig, Interceptor


class BaseClient(ABC):
    """Abstract base for LLM provider clients.

    Subclasses implement _provider_generate / _provider_generate_stream.
    The interceptor chain is handled here in the base.
    Supports async context manager protocol.
    """

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        _all = list(config.interceptors)
        self._before_interceptors: list[Interceptor] = [
            i for i in _all if hasattr(i, 'before_request')
        ]
        self._after_interceptors: list[Interceptor] = [
            i for i in _all if hasattr(i, 'after_response')
        ]

    # --- public API ---

    async def generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        """Generate a single response from the LLM.

        Args:
            messages: List of message dicts for the LLM.
            **kwargs: Provider-specific arguments.

        Returns:
            The native SDK response object.
        """
        messages, kwargs = await self._run_before(
            messages, kwargs
        )
        response = await self._provider_generate(
            messages, **kwargs
        )
        response = await self._run_after(response)
        return response

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Generate a streaming response from the LLM.

        Args:
            messages: List of message dicts for the LLM.
            **kwargs: Provider-specific arguments.

        Yields:
            Native SDK chunks.
        """
        messages, kwargs = await self._run_before(
            messages, kwargs
        )
        async for chunk in self._provider_generate_stream(
            messages, **kwargs
        ):
            yield chunk

    async def close(self) -> None:
        """Release resources. Override in subclasses."""

    # --- subclass hooks (internal) ---

    @abstractmethod
    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        """Generate a response via provider SDK.

        Args:
            messages: List of message dicts.
            **kwargs: Provider-specific arguments.

        Returns:
            The provider's native response object.
        """

    @abstractmethod
    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Stream responses via provider SDK.

        Args:
            messages: List of message dicts.
            **kwargs: Provider-specific arguments.

        Yields:
            The provider's native response chunks.
        """
        # yield required to make this an async generator.
        yield  # type: ignore[misc]  # pragma: no cover

    # --- interceptor chain (internal) ---

    def _build_init_kwargs(self) -> dict[str, Any]:
        """Build SDK init kwargs from config.

        Returns:
            Dict with api_key if configured.
        """
        _kwargs: dict[str, Any] = {}
        if self._config.api_key:
            _kwargs['api_key'] = self._config.api_key
        return _kwargs

    async def _run_before(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        for interceptor in self._before_interceptors:
            messages, kwargs = (
                await interceptor.before_request(
                    messages, kwargs
                )
            )
        return messages, kwargs

    async def _run_after(self, response: Any) -> Any:
        for interceptor in self._after_interceptors:
            response = (
                await interceptor.after_response(response)
            )
        return response

    # --- context manager ---

    async def __aenter__(self) -> BaseClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
