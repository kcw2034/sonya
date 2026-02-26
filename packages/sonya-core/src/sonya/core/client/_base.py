"""BaseClient ABC — 모든 Provider 클라이언트의 베이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from sonya.core._types import ClientConfig, Interceptor


class BaseClient(ABC):
    """LLM Provider 클라이언트 추상 베이스.

    - generate / generate_stream 만 구현하면 된다.
    - interceptor 체인은 베이스에서 처리한다.
    - async context manager 를 지원한다.
    """

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._interceptors: list[Interceptor] = list(config.interceptors)

    # --- public API ---

    async def generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        """단일 응답 생성. SDK 네이티브 응답을 그대로 반환한다."""
        messages, kwargs = await self._run_before(messages, kwargs)
        response = await self._do_generate(messages, **kwargs)
        response = await self._run_after(response)
        return response

    async def generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        """스트리밍 응답 생성. SDK 네이티브 청크를 yield 한다."""
        messages, kwargs = await self._run_before(messages, kwargs)
        async for chunk in self._do_generate_stream(messages, **kwargs):
            yield chunk

    # --- subclass hooks ---

    @abstractmethod
    async def _do_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        """Provider별 단일 응답 구현."""

    @abstractmethod
    async def _do_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        """Provider별 스트리밍 구현."""
        ...  # pragma: no cover
        # yield 를 포함해야 AsyncIterator 타입이 되므로 서브클래스에서 처리
        if False:  # noqa: SIM108
            yield  # type: ignore[misc]

    # --- interceptor chain ---

    async def _run_before(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        for i in self._interceptors:
            if hasattr(i, "before_request"):
                messages, kwargs = await i.before_request(messages, kwargs)
        return messages, kwargs

    async def _run_after(self, response: Any) -> Any:
        for i in self._interceptors:
            if hasattr(i, "after_response"):
                response = await i.after_response(response)
        return response

    # --- context manager ---

    async def __aenter__(self) -> BaseClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """리소스 정리. 서브클래스에서 오버라이드 가능."""
