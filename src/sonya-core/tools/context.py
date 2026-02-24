"""
ToolContext — Tool 간 공유 저장소
- run() 호출 동안 살아있는 key-value 저장소
- 코어는 값의 타입을 모른다 (Any). 외부 ML Tool이 자유롭게 저장/조회
- summary()로 LLM에 메타데이터만 전달 (값 자체는 전달하지 않음)
"""

from __future__ import annotations

from typing import Any, TypeVar, overload

_SENTINEL = object()
T = TypeVar("T")


class ToolContext:
    """
    Tool 간 데이터 공유를 위한 key-value 저장소

    사용법:
        ctx = ToolContext()
        ctx.set("query_vector", vector, source="embed_tool")
        vector = ctx.get("query_vector", expected_type=np.ndarray)
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def set(self, key: str, value: Any, *, source: str = "") -> None:
        """값을 저장한다. source는 출처 Tool 이름."""
        self._store[key] = value
        self._metadata[key] = {
            "type": type(value).__name__,
            "source": source,
        }

    @overload
    def get(self, key: str) -> Any: ...

    @overload
    def get(self, key: str, *, expected_type: type[T]) -> T: ...

    @overload
    def get(self, key: str, *, default: T) -> Any | T: ...

    def get(self, key: str, *, expected_type: type | None = None, default: Any = _SENTINEL) -> Any:
        """
        값을 조회한다.

        Args:
            key: 조회할 키
            expected_type: 기대하는 타입. 불일치 시 TypeError
            default: 키가 없을 때 반환할 기본값. 미지정 시 KeyError
        """
        if key not in self._store:
            if default is not _SENTINEL:
                return default
            raise KeyError(f"ToolContext에 '{key}' 키가 없습니다. 사용 가능한 키: {list(self._store.keys())}")

        value = self._store[key]

        if expected_type is not None and not isinstance(value, expected_type):
            raise TypeError(
                f"'{key}'의 타입이 {type(value).__name__}이지만, "
                f"{expected_type.__name__}을 기대했습니다."
            )

        return value

    def has(self, key: str) -> bool:
        """키가 존재하는지 확인"""
        return key in self._store

    def keys(self) -> list[str]:
        """저장된 모든 키 목록"""
        return list(self._store.keys())

    def summary(self) -> dict[str, str]:
        """
        LLM에 전달할 메타데이터 요약 (값 자체는 포함하지 않음)

        Returns:
            {"query_vector": "type=ndarray, source=embed_tool"} 같은 형태
        """
        result = {}
        for key, meta in self._metadata.items():
            parts = [f"type={meta['type']}"]
            if meta.get("source"):
                parts.append(f"source={meta['source']}")
            result[key] = ", ".join(parts)
        return result

    def clear(self) -> None:
        """저장소 초기화"""
        self._store.clear()
        self._metadata.clear()

    def __repr__(self) -> str:
        return f"ToolContext(keys={self.keys()})"
