"""sonya.pipeline.types — 파이프라인 프로토콜 정의

파이프라인 스테이지와 외부 데이터 소스 어댑터를 위한
확장 가능한 프로토콜 기반 추상화.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ── 메시지 타입 ────────────────────────────────────────────────────────────

# sonya-core 의 Agent.run() 이 받는 메시지 포맷과 동일
Message = dict[str, Any]


# ── 파이프라인 스테이지 프로토콜 ────────────────────────────────────────────

@runtime_checkable
class PipelineStage(Protocol):
    """메시지 리스트를 변환하는 파이프라인 스테이지.

    각 스테이지는 메시지 리스트를 받아 변환된 메시지 리스트를 반환한다.
    필터링, 요약, 토큰 제한, 시스템 프롬프트 주입 등에 활용.

    Example::

        class MyStage:
            def process(self, messages):
                return [m for m in messages if m["role"] != "system"]
    """

    def process(self, messages: list[Message]) -> list[Message]:
        """메시지 리스트를 변환하여 반환한다."""
        ...


# ── 소스 어댑터 프로토콜 ───────────────────────────────────────────────────

@runtime_checkable
class SourceAdapter(Protocol):
    """외부 데이터 소스에서 메시지를 가져오는 어댑터.

    파일, DB, API 등 다양한 외부 소스로부터 대화 데이터를
    sonya 표준 메시지 포맷으로 변환하여 가져온다.

    Example::

        class JsonFileAdapter:
            def __init__(self, path: str):
                self._path = path

            def fetch(self) -> list[dict]:
                with open(self._path) as f:
                    return json.load(f)
    """

    def fetch(self) -> list[Message]:
        """외부 소스에서 메시지 리스트를 가져온다."""
        ...
