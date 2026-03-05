"""sonya.pipeline.bridge — ContextBridge (sonya-pack ↔ sonya-core)

BinContextEngine 과 sonya-core Agent 사이의 데이터 흐름을 연결하는 브릿지.
Agent 실행에 필요한 메시지 리스트를 BinContext 에서 JIT 복원하고,
Agent 실행 결과를 다시 BinContext 에 기록한다.
"""

from __future__ import annotations

from typing import Any

from sonya.pack import BinContextEngine
from sonya.pipeline.types import Message


class ContextBridge:
    """sonya-pack(BinContext)과 sonya-core(Agent) 사이의 데이터 브릿지.

    BinContext 엔진을 감싸서 sonya-core Agent.run() 에 바로 전달할 수 있는
    메시지 리스트를 제공하고, 실행 결과를 다시 저장한다.

    Parameters:
        engine: 주입할 BinContextEngine 인스턴스.

    Example::

        from sonya.pack import BinContextEngine
        from sonya.pipeline import ContextBridge

        engine = BinContextEngine("./data")
        bridge = ContextBridge(engine)
        bridge.save_messages("sess-1", [
            {"role": "user", "content": "안녕!"},
        ])
        context = bridge.load_context("sess-1")
        # → Agent.run(context) 로 바로 사용 가능
    """

    def __init__(self, engine: BinContextEngine) -> None:
        self._engine = engine

    @property
    def engine(self) -> BinContextEngine:
        """내부 BinContextEngine 인스턴스를 반환한다."""
        return self._engine

    # ── 저장 ───────────────────────────────────────────────────────────────

    def save_messages(
        self,
        session_id: str,
        messages: list[Message],
    ) -> int:
        """메시지 리스트를 BinContext 에 일괄 저장한다.

        Args:
            session_id: 대화 세션 식별자.
            messages: ``[{"role": "user", "content": "..."}]`` 형태의 리스트.

        Returns:
            저장된 메시지 수.
        """
        count = 0
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:  # 빈 메시지는 무시
                self._engine.add_message(session_id, role, content)
                count += 1
        return count

    def save_agent_result(
        self,
        session_id: str,
        result: Any,
    ) -> None:
        """sonya-core AgentResult 를 BinContext 에 기록한다.

        AgentResult.text 를 assistant 메시지로 저장한다.

        Args:
            session_id: 대화 세션 식별자.
            result: sonya-core 의 ``AgentResult`` 인스턴스.
        """
        # AgentResult 의 text 필드를 assistant 메시지로 기록
        text = getattr(result, "text", None)
        if text:
            self._engine.add_message(session_id, "assistant", text)

    # ── 로드 ───────────────────────────────────────────────────────────────

    def load_context(
        self,
        session_id: str,
        *,
        last_n_turns: int | None = None,
    ) -> list[Message]:
        """BinContext 에서 대화 컨텍스트를 JIT 복원한다.

        반환되는 ``list[dict]`` 는 sonya-core ``Agent.run(messages)`` 에
        직접 전달 가능한 포맷이다.

        Args:
            session_id: 대화 세션 식별자.
            last_n_turns: 최근 N 개 메시지만 가져올 경우 지정.

        Returns:
            ``[{"role": "user", "content": "..."}, ...]`` 형태의 리스트.
        """
        return self._engine.build_context(
            session_id, last_n_turns=last_n_turns
        )

    # ── 유틸리티 ───────────────────────────────────────────────────────────

    def list_sessions(self) -> list[str]:
        """등록된 모든 세션 ID 목록을 반환한다."""
        return self._engine.list_sessions()

    def message_count(self, session_id: str) -> int:
        """해당 세션의 메시지 수를 반환한다."""
        session = self._engine.get_session(session_id)
        return len(session.messages)
