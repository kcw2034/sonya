"""Internal helper to create handoff tools."""

from __future__ import annotations

from typing import Any

from sonya.core.models.agent import Agent
from sonya.core.models.prompt import Prompt
from sonya.core.models.tool import Tool

_HANDOFF_PREFIX = '__handoff_to_'


def _instructions_preview(
    instructions: str | Prompt | None,
) -> str:
    """Return a truncated plain-text preview of instructions.

    Handles both ``str`` and :class:`Prompt` types safely.

    Args:
        instructions: Agent instructions (str, Prompt, or None).

    Returns:
        Up to 100 characters of rendered instructions text.
    """
    if not instructions:
        return ''
    if isinstance(instructions, Prompt):
        return instructions.render()[:100]
    return instructions[:100]


def _make_handoff_tool(target: Agent) -> Tool:
    """Create a tool that triggers a handoff to *target* agent.

    The tool name uses a reserved prefix so the runtime can detect
    it and interrupt the execution loop.

    Args:
        target: The agent to hand off to.

    Returns:
        A :class:`Tool` that, when called, returns a handoff marker.
    """

    async def _handoff_fn(**kwargs: Any) -> str:
        return f'Handing off to {target.name}'

    return Tool(
        name=f'{_HANDOFF_PREFIX}{target.name}',
        description=(
            f'Hand off the conversation to the '
            f'"{target.name}" agent. '
            f'{_instructions_preview(target.instructions)}'
        ),
        fn=_handoff_fn,
        schema={
            'type': 'object',
            'properties': {},
        },
    )
