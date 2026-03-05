#!/usr/bin/env python3
"""pipeline_usage.py — sonya-pipeline 기본 사용 예제

이 스크립트는 다음 과정을 시연합니다:
  1. BinContextEngine → ContextBridge 연결
  2. 메시지 일괄 저장 (save_messages)
  3. Pipeline 스테이지 체인 구성 (SystemPrompt + Truncate)
  4. JIT 컨텍스트 로드 → 파이프라인 변환 → 최종 결과 출력
  5. AgentResult 저장 시뮬레이션
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from sonya.pack import BinContextEngine
from sonya.pipeline import (
    ContextBridge,
    FilterByRoleStage,
    Pipeline,
    SystemPromptStage,
    TruncateStage,
)


@dataclass
class MockAgentResult:
    """sonya-core AgentResult 를 모방하는 목 객체."""

    agent_name: str
    text: str


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pipeline_") as tmp:
        data_dir = Path(tmp) / "store"
        engine = BinContextEngine(data_dir)
        bridge = ContextBridge(engine)

        print("=" * 60)
        print("  sonya-pipeline — 데이터 파이프라인 예제")
        print("=" * 60)

        # ── 1) ContextBridge 로 메시지 일괄 저장 ─────────────────────────
        session_id = "demo-session"
        messages = [
            {"role": "user", "content": "파이썬에서 비동기 프로그래밍이 뭔가요?"},
            {"role": "assistant", "content": "비동기 프로그래밍은 I/O 바운드 작업을 효율적으로 처리하는 방식입니다."},
            {"role": "user", "content": "asyncio 라이브러리 사용법을 알려주세요."},
            {"role": "assistant", "content": "asyncio는 async/await 구문을 사용하여 코루틴을 실행합니다."},
            {"role": "user", "content": "실제 예제 코드를 보여주세요."},
            {"role": "assistant", "content": "import asyncio\n\nasync def main():\n    await asyncio.sleep(1)\n    print('완료!')"},
            {"role": "user", "content": "동시에 여러 작업을 실행하려면?"},
        ]

        saved_count = bridge.save_messages(session_id, messages)
        print(f"\n📥 저장된 메시지: {saved_count}개")
        print(f"📊 세션 메시지 수: {bridge.message_count(session_id)}개")

        # ── 2) Pipeline 구성 ─────────────────────────────────────────────
        pipeline = (
            Pipeline()
            .add_stage(SystemPromptStage("당신은 파이썬 전문 AI 튜터입니다."))
            .add_stage(TruncateStage(max_turns=4))
        )
        print(f"\n🔧 파이프라인: {pipeline}")

        # ── 3) JIT 로드 → 파이프라인 변환 ────────────────────────────────
        raw_context = bridge.load_context(session_id)
        print(f"\n── 원본 컨텍스트 ({len(raw_context)}개 메시지) ──")
        for msg in raw_context:
            print(f"  [{msg['role']:>9}] {msg['content'][:50]}...")

        transformed = pipeline.run(raw_context)
        print(f"\n── 변환 후 (system + 최근 4턴 = {len(transformed)}개) ──")
        for msg in transformed:
            icon = {"system": "⚙️", "user": "👤", "assistant": "🤖"}.get(msg["role"], "❓")
            print(f"  {icon} [{msg['role']:>9}] {msg['content'][:50]}")

        # ── 4) AgentResult 저장 시뮬레이션 ───────────────────────────────
        print("\n── AgentResult 저장 ──")
        mock_result = MockAgentResult(
            agent_name="tutor-agent",
            text="asyncio.gather()를 사용하면 여러 코루틴을 동시에 실행할 수 있습니다.",
        )
        bridge.save_agent_result(session_id, mock_result)
        print(f"  ✅ 에이전트 응답 저장 완료 (메시지 수: {bridge.message_count(session_id)})")

        # 저장된 결과 확인
        last_msg = bridge.load_context(session_id, last_n_turns=1)
        print(f"  🤖 저장된 응답: {last_msg[0]['content']}")

        # ── 5) FilterByRoleStage 시연 ────────────────────────────────────
        print("\n── FilterByRoleStage (user 만 필터) ──")
        user_only = Pipeline().add_stage(FilterByRoleStage(roles=("user",)))
        user_msgs = user_only.run(raw_context)
        for msg in user_msgs:
            print(f"  👤 {msg['content'][:60]}")

        print(f"\n✅ 모든 파이프라인 예제가 정상적으로 실행되었습니다!")


if __name__ == "__main__":
    main()
