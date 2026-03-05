#!/usr/bin/env python3
"""basic_usage.py — BinContext 엔진 기본 사용 예제

이 스크립트는 다음 과정을 시연합니다:
  1. 엔진 초기화 (임시 디렉토리)
  2. 다중 세션에 메시지 추가 (Append-Only Binary Log)
  3. JIT Context Builder 를 통한 전체/최근 N 턴 컨텍스트 복원
  4. 세션 메타데이터 조회
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from sonya.pack import BinContextEngine


def main() -> None:
    # ── 1) 엔진 초기화 ────────────────────────────────────────────────────
    # 임시 디렉토리를 사용하여 예제 실행 후 자동 정리
    with tempfile.TemporaryDirectory(prefix="binctx_") as tmp:
        data_dir = Path(tmp) / "store"
        engine = BinContextEngine(data_dir)

        print("=" * 60)
        print("  BinContext Engine — 기본 사용 예제")
        print("=" * 60)

        # ── 2) 메시지 추가 ────────────────────────────────────────────────
        session_id = "chat-001"

        engine.add_message(session_id, "system", "당신은 친절한 AI 어시스턴트입니다.")
        engine.add_message(session_id, "user", "안녕하세요! 파이썬에 대해 알려주세요.")
        engine.add_message(
            session_id,
            "assistant",
            "안녕하세요! 파이썬은 배우기 쉽고 강력한 프로그래밍 언어입니다. "
            "데이터 과학, 웹 개발, AI 등 다양한 분야에서 활용됩니다.",
        )
        engine.add_message(session_id, "user", "가장 인기 있는 라이브러리는 뭔가요?")
        engine.add_message(
            session_id,
            "assistant",
            "인기 있는 파이썬 라이브러리로는 NumPy, Pandas, TensorFlow, "
            "FastAPI 등이 있습니다.",
        )

        print(f"\n📁 데이터 디렉토리: {data_dir}")
        print(f"📦 .bin 파일 크기: {(data_dir / 'context.bin').stat().st_size} bytes")

        # ── 3) 전체 컨텍스트 복원 (JIT) ───────────────────────────────────
        print("\n── 전체 대화 컨텍스트 ──")
        full_context = engine.build_context(session_id)
        for msg in full_context:
            role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖"}
            icon = role_icon.get(msg["role"], "❓")
            print(f"  {icon} [{msg['role']:>9}] {msg['content'][:60]}...")

        # ── 4) 최근 2턴만 복원 ────────────────────────────────────────────
        print("\n── 최근 2턴 컨텍스트 (last_n_turns=2) ──")
        recent = engine.build_context(session_id, last_n_turns=2)
        for msg in recent:
            role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖"}
            icon = role_icon.get(msg["role"], "❓")
            print(f"  {icon} [{msg['role']:>9}] {msg['content']}")

        # ── 5) 세션 메타데이터 조회 ────────────────────────────────────────
        print("\n── 세션 메타데이터 ──")
        session = engine.get_session(session_id)
        print(f"  세션 ID : {session.session_id}")
        print(f"  메시지 수: {len(session.messages)}")
        for i, meta in enumerate(session.messages):
            print(
                f"    [{i}] role={meta.role:>9}  "
                f"offset={meta.offset:>4}  length={meta.length:>4}  "
                f"id={meta.message_id[:8]}…"
            )

        # ── 6) 메타데이터 영속화 확인 ─────────────────────────────────────
        print("\n── 메타데이터 영속성 확인 ──")
        # 새 엔진 인스턴스로 동일 디렉토리를 열어 데이터가 복원되는지 검증
        engine2 = BinContextEngine(data_dir)
        restored = engine2.build_context(session_id, last_n_turns=1)
        print(f"  복원된 마지막 메시지: {restored[0]['content']}")

        print("\n✅ 모든 예제가 정상적으로 실행되었습니다!")


if __name__ == "__main__":
    main()
