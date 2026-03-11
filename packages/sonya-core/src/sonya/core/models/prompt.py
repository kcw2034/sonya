"""Structured prompt types for agent instructions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Example:
    """Few-shot example pair.

    Args:
        user: User message content.
        assistant: Expected assistant response.
    """

    user: str
    assistant: str
