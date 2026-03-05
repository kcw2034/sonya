"""sonya.pack.engine — BinContext 핵심 엔진

Append-Only Binary Log + Metadata Index + JIT Context Builder 아키텍처의
코어 구현체.  `.bin` 파일에는 순수 UTF-8 바이트만 저장되며, 별도의
메타데이터 인덱스가 각 메시지의 오프셋/길이를 추적한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict

from sonya.pack.schema import MessageMeta, SessionIndex


# ── 타입 힌트 ──────────────────────────────────────────────────────────────

class MessageDict(TypedDict):
    """build_context 가 반환하는 개별 메시지 딕셔너리."""

    role: str
    content: str


# ── BinContext 엔진 ────────────────────────────────────────────────────────

class BinContextEngine:
    """초경량 바이너리 컨텍스트 엔진.

    Parameters:
        data_dir: `.bin` 파일과 메타데이터 JSON 을 저장할 디렉토리 경로.

    Example::

        engine = BinContextEngine("./data")
        engine.add_message("sess-1", "user", "안녕하세요!")
        context = engine.build_context("sess-1", last_n_turns=5)
    """

    # 상수
    _BIN_FILENAME = "context.bin"
    _META_FILENAME = "metadata.json"

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._bin_path = self._data_dir / self._BIN_FILENAME
        self._meta_path = self._data_dir / self._META_FILENAME

        # 세션 인덱스 — 메모리에서 관리, 필요 시 JSON 으로 영속화
        self._sessions: dict[str, SessionIndex] = {}

        # 기존 메타데이터가 있으면 로드
        if self._meta_path.exists():
            self._load_metadata()

    # ── Public API ─────────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        text: str,
        *,
        token_count: int | None = None,
    ) -> MessageMeta:
        """텍스트를 바이너리 로그에 Append 하고 메타데이터를 업데이트한다.

        Args:
            session_id: 대화 세션 식별자.
            role: 발화자 ("user" | "assistant" | "system").
            text: 저장할 메시지 원문.
            token_count: (선택) 추정 토큰 수.

        Returns:
            생성된 `MessageMeta` 인스턴스.
        """
        # 1) UTF-8 인코딩
        data = text.encode("utf-8")

        # 2) Append-Only 쓰기 — 현재 파일 끝 위치가 곧 오프셋
        with open(self._bin_path, "ab") as f:
            offset = f.tell()          # 파일 끝 = 새 데이터 시작 위치
            f.write(data)

        # 3) 메타데이터 생성
        meta = MessageMeta(
            role=role,
            offset=offset,
            length=len(data),
            token_count=token_count,
        )

        # 4) 세션 인덱스 업데이트
        session = self._ensure_session(session_id)
        session.messages.append(meta)

        # 5) 메타데이터 영속화
        self._save_metadata()

        return meta

    def build_context(
        self,
        session_id: str,
        *,
        last_n_turns: int | None = None,
    ) -> list[MessageDict]:
        """JIT 방식으로 바이너리 로그에서 대화 컨텍스트를 복원한다.

        메타데이터를 기반으로 `.bin` 파일의 특정 바이트 구간만 읽어
        텍스트로 디코딩하여 프롬프트 리스트를 구성한다.

        Args:
            session_id: 대화 세션 식별자.
            last_n_turns: 최근 N 개 메시지만 가져올 경우 지정.
                          `None` 이면 전체 대화를 반환.

        Returns:
            `[{"role": "user", "content": "..."}, ...]` 형태의 리스트.

        Raises:
            KeyError: 존재하지 않는 세션 ID.
            FileNotFoundError: `.bin` 파일이 없을 때.
        """
        session = self._get_session(session_id)
        targets = session.messages

        # 최근 N 턴 필터링
        if last_n_turns is not None and last_n_turns > 0:
            targets = targets[-last_n_turns:]

        # JIT 읽기 — seek/read 기반 O(1) 접근
        result: list[MessageDict] = []
        with open(self._bin_path, "rb") as f:
            for meta in targets:
                f.seek(meta.offset)
                raw = f.read(meta.length)
                content = raw.decode("utf-8")
                result.append(MessageDict(role=meta.role, content=content))

        return result

    def get_session(self, session_id: str) -> SessionIndex:
        """세션 메타데이터를 조회한다.

        Args:
            session_id: 대화 세션 식별자.

        Returns:
            해당 세션의 `SessionIndex`.

        Raises:
            KeyError: 존재하지 않는 세션 ID.
        """
        return self._get_session(session_id)

    def list_sessions(self) -> list[str]:
        """등록된 모든 세션 ID 목록을 반환한다."""
        return list(self._sessions.keys())

    # ── 메타데이터 영속화 ──────────────────────────────────────────────────

    def _save_metadata(self) -> None:
        """전체 세션 인덱스를 JSON 파일로 저장한다."""
        payload = {
            sid: session.model_dump(mode="json")
            for sid, session in self._sessions.items()
        }
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _load_metadata(self) -> None:
        """JSON 파일에서 세션 인덱스를 복원한다."""
        with open(self._meta_path, encoding="utf-8") as f:
            payload: dict = json.load(f)
        for sid, data in payload.items():
            self._sessions[sid] = SessionIndex.model_validate(data)

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────────

    def _ensure_session(self, session_id: str) -> SessionIndex:
        """세션이 없으면 생성하고, 있으면 기존 인스턴스를 반환한다."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionIndex(session_id=session_id)
        return self._sessions[session_id]

    def _get_session(self, session_id: str) -> SessionIndex:
        """세션을 조회하되, 없으면 KeyError 를 발생시킨다."""
        try:
            return self._sessions[session_id]
        except KeyError:
            raise KeyError(
                f"세션 '{session_id}'을(를) 찾을 수 없습니다. "
                f"등록된 세션: {self.list_sessions()}"
            ) from None
