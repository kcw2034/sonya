"""sonya.pack.schemas.schema — BinContext metadata schema definitions

Pydantic v2 based strict definitions for message pointers (MessageMeta)
and session indices (SessionIndex).
All fields are declared as frozen to guarantee runtime integrity.
"""

from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class MessageMeta(BaseModel, frozen=True):
    """Individual message pointer to a position in the binary file.

    Attributes:
        message_id: Unique message identifier (UUID v4).
        role: Message speaker — one of "user", "assistant",
            "system".
        offset: Start byte position in the .bin file.
        length: Number of bytes to read.
        timestamp: Message creation time (Unix epoch seconds).
        token_count: (Optional) Estimated token count for
            context window optimization.
    """

    message_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex
    )
    role: Literal['user', 'assistant', 'system']
    offset: int = Field(ge=0)
    length: int = Field(gt=0)
    timestamp: float = Field(default_factory=time.time)
    token_count: int | None = Field(default=None, ge=0)


class SessionIndex(BaseModel):
    """Collection of message metadata for a single session.

    Attributes:
        session_id: Unique session (conversation) identifier.
        messages: Time-ordered list of message pointers.
    """

    session_id: str
    messages: list[MessageMeta] = Field(default_factory=list)
