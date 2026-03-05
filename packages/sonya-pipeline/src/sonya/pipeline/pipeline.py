"""sonya.pipeline.pipeline — 파이프라인 엔진 및 내장 스테이지

메시지 리스트를 순차적인 스테이지 체인으로 변환하는 파이프라인 엔진과
즉시 사용 가능한 내장 스테이지를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sonya.pipeline.types import Message, PipelineStage


# ── 파이프라인 엔진 ────────────────────────────────────────────────────────

class Pipeline:
    """순차적 스테이지 체인으로 메시지를 변환하는 파이프라인 엔진.

    각 스테이지는 ``PipelineStage`` 프로토콜을 구현하며,
    ``add_stage()`` 로 등록된 순서대로 메시지 리스트를 변환한다.

    Example::

        pipeline = Pipeline()
        pipeline.add_stage(SystemPromptStage("당신은 AI 도우미입니다."))
        pipeline.add_stage(TruncateStage(max_turns=10))
        result = pipeline.run(messages)
    """

    def __init__(self) -> None:
        self._stages: list[PipelineStage] = []

    def add_stage(self, stage: PipelineStage) -> "Pipeline":
        """스테이지를 파이프라인 끝에 추가한다.

        Args:
            stage: ``PipelineStage`` 프로토콜을 구현하는 객체.

        Returns:
            메서드 체이닝을 위해 자기 자신을 반환한다.
        """
        self._stages.append(stage)
        return self

    def run(self, messages: list[Message]) -> list[Message]:
        """등록된 모든 스테이지를 순차 실행하여 메시지를 변환한다.

        Args:
            messages: 입력 메시지 리스트.

        Returns:
            모든 스테이지를 거친 변환된 메시지 리스트.
        """
        result = list(messages)  # 원본 보호를 위한 얕은 복사
        for stage in self._stages:
            result = stage.process(result)
        return result

    @property
    def stages(self) -> list[PipelineStage]:
        """등록된 스테이지 목록을 반환한다."""
        return list(self._stages)

    def __len__(self) -> int:
        return len(self._stages)

    def __repr__(self) -> str:
        names = [type(s).__name__ for s in self._stages]
        return f"Pipeline(stages={names})"


# ── 내장 스테이지 ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TruncateStage:
    """최근 N 턴만 유지하는 트렁케이션 스테이지.

    system 메시지는 트렁케이션 대상에서 제외되어 항상 보존된다.

    Args:
        max_turns: 유지할 최대 메시지 수 (system 메시지 제외).
    """

    max_turns: int

    def process(self, messages: list[Message]) -> list[Message]:
        # system 메시지와 비-system 메시지 분리
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 최근 N 턴만 유지
        truncated = non_system[-self.max_turns:]

        # system 메시지를 앞에 붙여서 반환
        return system_msgs + truncated


@dataclass(frozen=True, slots=True)
class SystemPromptStage:
    """시스템 프롬프트를 메시지 리스트 앞에 삽입하는 스테이지.

    기존에 system 메시지가 있으면 교체하고, 없으면 추가한다.

    Args:
        prompt: 삽입할 시스템 프롬프트 텍스트.
    """

    prompt: str

    def process(self, messages: list[Message]) -> list[Message]:
        # 기존 system 메시지 제거
        filtered = [m for m in messages if m.get("role") != "system"]
        # 새 system 메시지를 앞에 삽입
        return [{"role": "system", "content": self.prompt}] + filtered


@dataclass(frozen=True, slots=True)
class FilterByRoleStage:
    """특정 역할의 메시지만 유지하는 필터 스테이지.

    Args:
        roles: 유지할 역할 목록 (예: ["user", "assistant"]).
    """

    roles: tuple[str, ...] = ("user", "assistant")

    def process(self, messages: list[Message]) -> list[Message]:
        return [m for m in messages if m.get("role") in self.roles]


@dataclass(frozen=True, slots=True)
class MetadataInjectionStage:
    """각 메시지에 메타데이터를 주입하는 스테이지.

    메시지 딕셔너리에 지정된 키-값 쌍을 추가한다.
    기존 키와 충돌하는 경우 덮어쓰지 않는다.

    Args:
        metadata: 주입할 메타데이터 딕셔너리.
    """

    metadata: dict[str, str] = field(default_factory=dict)

    def process(self, messages: list[Message]) -> list[Message]:
        result = []
        for msg in messages:
            enriched = dict(msg)
            for key, value in self.metadata.items():
                enriched.setdefault(key, value)  # 기존 키 보호
            result.append(enriched)
        return result
