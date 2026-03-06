"""
히스토리 트리밍 / 요약 전략
- 토큰 예산 또는 메시지 수 초과 시 오래된 메시지 제거
- tool_use/tool_result 쌍을 원자적으로 유지하는 슬라이딩 윈도우
- 제거 구간을 LLM으로 요약하여 합성 메시지로 대체 (옵션)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...llm.models import Message
from ...utils.runtime.history import (
    _estimate_tokens,
    _find_split_index,
    _summarize_messages,
)

if TYPE_CHECKING:
    from ...llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


@dataclass
class HistoryConfig:
    """히스토리 관리 설정"""

    # 토큰 예산 (primary trigger)
    max_tokens: int | None = 80_000
    # 메시지 수 상한 (secondary safety)
    max_messages: int | None = 100
    # 보존할 최신 턴 수 (턴 = user+assistant 쌍)
    keep_recent: int = 10
    # 요약 활성화 여부
    summarize: bool = True
    # 요약 응답 최대 토큰
    summary_max_tokens: int = 512
    # 토큰 추정 비율 (문자 수 / 토큰)
    chars_per_token: float = 3.5


class _SummaryOutput(BaseModel):
    """요약 결과 스키마"""

    summary: str


class HistoryManager:
    """
    대화 히스토리를 관리하고, 토큰 예산 초과 시 트리밍/요약을 수행

    사용법:
        config = HistoryConfig(max_tokens=40_000)
        mgr = HistoryManager(config, client)
        mgr.append(Message(role="user", content="안녕"))
        await mgr.maybe_trim()
    """

    def __init__(
        self,
        config: HistoryConfig | None = None,
        client: BaseLLMClient | None = None,
    ):
        self._config = config or HistoryConfig()
        self._client = client
        self._messages: list[Message] = []
        self._last_input_tokens: int | None = None

    @property
    def messages(self) -> list[Message]:
        """현재 히스토리 (읽기 전용 복사본)"""
        return list(self._messages)

    def append(self, message: Message) -> None:
        """메시지 추가"""
        self._messages.append(message)

    def update_token_count(self, input_tokens: int) -> None:
        """LLM 응답의 실제 input_tokens를 기록하여 추정 정확도 개선"""
        self._last_input_tokens = input_tokens

    def to_api_messages(self) -> list[dict]:
        """API 포맷으로 직렬화"""
        return [m.to_api_dict() for m in self._messages]

    def reset(self) -> None:
        """히스토리 초기화"""
        self._messages.clear()
        self._last_input_tokens = None

    async def maybe_trim(self) -> bool:
        """
        트리밍 조건 확인 후 필요 시 실행

        Returns:
            트리밍이 실행되었으면 True
        """
        cfg = self._config

        # 조건 1: 토큰 예산 초과
        over_tokens = False
        if cfg.max_tokens is not None:
            estimated = _estimate_tokens(
                self._messages,
                cfg.chars_per_token,
                self._last_input_tokens,
            )
            over_tokens = estimated > cfg.max_tokens

        # 조건 2: 메시지 수 초과
        over_messages = False
        if cfg.max_messages is not None:
            over_messages = len(self._messages) > cfg.max_messages

        if not over_tokens and not over_messages:
            return False

        split_idx = _find_split_index(
            self._messages,
            cfg.keep_recent,
            cfg.max_tokens,
            cfg.max_messages,
            lambda messages: _estimate_tokens(
                messages,
                cfg.chars_per_token,
                self._last_input_tokens,
            ),
        )
        if split_idx <= 0:
            logger.debug("트리밍 가능한 분리점을 찾지 못했습니다.")
            return False

        # 제거할 메시지 구간
        removed = self._messages[:split_idx]
        kept = self._messages[split_idx:]

        # 요약 시도
        summary_msg: Message | None = None
        if cfg.summarize and self._client is not None and len(removed) > 0:
            summary_msg = await _summarize_messages(
                self._client,
                removed,
                _SummaryOutput,
            )

        # 히스토리 재구성
        if summary_msg is not None:
            self._messages = [summary_msg] + kept
        else:
            # 요약 실패 또는 비활성 — 폴백 메시지 삽입
            fallback = Message(
                role="user",
                content="[이전 대화 내용 생략]",
            )
            self._messages = [fallback] + kept

        logger.info(
            f"히스토리 트리밍 완료: {len(removed)}개 메시지 제거, "
            f"현재 {len(self._messages)}개 메시지"
        )
        return True
