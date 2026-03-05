"""sonya.pack.schema — BinContext 메타데이터 스키마 정의

Pydantic v2 기반으로 메시지 포인터(MessageMeta)와
세션 인덱스(SessionIndex)를 엄격하게 정의한다.
모든 필드는 불변(frozen)으로 선언하여 런타임 무결성을 보장한다.
"""

from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class MessageMeta(BaseModel, frozen=True):
    """개별 메시지의 바이너리 파일 내 위치를 가리키는 포인터.

    Attributes:
        message_id: 메시지 고유 식별자 (UUID v4).
        role: 메시지 발화자 — "user", "assistant", "system" 중 하나.
        offset: .bin 파일 내 시작 바이트 위치.
        length: 읽어야 할 바이트 수.
        timestamp: 메시지 생성 시각 (Unix epoch seconds).
        token_count: (선택) 해당 메시지의 추정 토큰 수 — 컨텍스트 윈도우 최적화용.
    """

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    role: Literal["user", "assistant", "system"]
    offset: int = Field(ge=0)
    length: int = Field(gt=0)
    timestamp: float = Field(default_factory=time.time)
    token_count: int | None = Field(default=None, ge=0)


class SessionIndex(BaseModel):
    """하나의 대화 세션에 속한 메시지 메타데이터 모음.

    Attributes:
        session_id: 세션(대화방) 고유 식별자.
        messages: 시간순으로 정렬된 메시지 포인터 리스트.
    """

    session_id: str
    messages: list[MessageMeta] = Field(default_factory=list)
