"""sonya.pack.schemas.schema — BinContext metadata schema definitions

Pydantic v2 based strict definitions for message pointers (MessageMeta)
and session indices (SessionIndex).
All fields are declared as frozen to guarantee runtime integrity.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Discriminator, Field, Tag

from sonya.core.schemas.memory import MemoryType


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
        memory_type: Memory hierarchy classification.
    """

    message_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex
    )
    role: Literal['user', 'assistant', 'system']
    offset: int = Field(ge=0)
    length: int = Field(gt=0)
    timestamp: float = Field(default_factory=time.time)
    token_count: int | None = Field(default=None, ge=0)
    memory_type: MemoryType = Field(
        default=MemoryType.EPISODIC
    )

    @property
    def content(self) -> str:
        """Raw text content placeholder.

        Actual content resides in the .bin file, not in metadata.
        Returns empty string to satisfy MemoryEntry protocol.
        """
        return ''


class EpisodicMeta(MessageMeta):
    """Episodic memory metadata.

    Attributes:
        event_tag: Short label for the event.
        outcome: Success/failure indicator.
        related_session_id: Link to another session.
    """

    memory_type: MemoryType = Field(
        default=MemoryType.EPISODIC
    )
    event_tag: str | None = None
    outcome: str | None = None
    related_session_id: str | None = None


class ProceduralMeta(MessageMeta):
    """Procedural memory metadata.

    Attributes:
        workflow_name: Name of the workflow/playbook.
        step_order: Step sequence number.
        trigger: Condition that activates this procedure.
    """

    memory_type: MemoryType = Field(
        default=MemoryType.PROCEDURAL
    )
    workflow_name: str | None = None
    step_order: int | None = None
    trigger: str | None = None


class SemanticMeta(MessageMeta):
    """Semantic memory metadata.

    Attributes:
        category: Knowledge domain category.
        keywords: Searchable keyword tags.
        source_episode_id: Episode this was distilled from.
    """

    memory_type: MemoryType = Field(
        default=MemoryType.SEMANTIC
    )
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    source_episode_id: str | None = None


def _meta_discriminator(v: Any) -> str:
    """Discriminator function for MetaUnion.

    Args:
        v: Raw value (dict during parsing, model after).

    Returns:
        String value of the memory_type enum member.
    """
    if isinstance(v, dict):
        mt = v.get('memory_type', 'episodic')
        if isinstance(mt, MemoryType):
            return mt.value
        return mt
    return v.memory_type.value


MetaUnion = Annotated[
    Union[
        Annotated[EpisodicMeta, Tag('episodic')],
        Annotated[ProceduralMeta, Tag('procedural')],
        Annotated[SemanticMeta, Tag('semantic')],
    ],
    Discriminator(_meta_discriminator),
]


class SessionIndex(BaseModel):
    """Collection of message metadata for a single session.

    Attributes:
        session_id: Unique session (conversation) identifier.
        messages: Time-ordered list of message pointers.
    """

    session_id: str
    messages: list[MetaUnion] = Field(default_factory=list)
