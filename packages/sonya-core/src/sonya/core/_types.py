"""Interceptor 프로토콜 및 공통 타입 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Interceptor(Protocol):
    """API 호출 전후 가로채기 프로토콜.

    before_request / after_response 중 필요한 것만 구현하면 된다.
    """

    async def before_request(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """요청 전 메시지와 kwargs를 변환할 수 있다."""
        ...

    async def after_response(self, response: Any) -> Any:
        """응답을 변환하거나 로깅할 수 있다."""
        ...


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """클라이언트 공통 설정."""

    model: str
    api_key: str | None = None
    interceptors: list[Interceptor] = field(default_factory=list)
