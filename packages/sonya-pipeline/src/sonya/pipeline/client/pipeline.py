"""sonya.pipeline.client.pipeline — Pipeline engine and built-in stages.

Provides a pipeline engine that transforms message lists through
a sequential chain of stages, along with ready-to-use built-in stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sonya.pipeline.schemas.types import Message, PipelineStage


# ── Pipeline engine ──────────────────────────────────────────────────────

class Pipeline:
    """Pipeline engine that transforms messages through a sequential
    stage chain.

    Each stage implements the ``PipelineStage`` protocol and
    transforms the message list in the order registered via
    ``add_stage()``.

    Example::

        pipeline = Pipeline()
        pipeline.add_stage(
            SystemPromptStage('You are an AI assistant.')
        )
        pipeline.add_stage(TruncateStage(max_turns=10))
        result = pipeline.run(messages)
    """

    def __init__(self) -> None:
        self._stages: list[PipelineStage] = []

    def add_stage(self, stage: PipelineStage) -> 'Pipeline':
        """Append a stage to the end of the pipeline.

        Args:
            stage: An object implementing the
                ``PipelineStage`` protocol.

        Returns:
            Self for method chaining.
        """
        self._stages.append(stage)
        return self

    def run(
        self, messages: list[Message]
    ) -> list[Message]:
        """Run all registered stages sequentially to transform
        messages.

        Args:
            messages: Input message list.

        Returns:
            Transformed message list after all stages.
        """
        result = list(messages)
        for stage in self._stages:
            result = stage.process(result)
        return result

    @property
    def stages(self) -> list[PipelineStage]:
        """Return the list of registered stages."""
        return list(self._stages)

    def __len__(self) -> int:
        return len(self._stages)

    def __repr__(self) -> str:
        names = [type(s).__name__ for s in self._stages]
        return f'Pipeline(stages={names})'


# ── Built-in stages ─────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TruncateStage:
    """Truncation stage that keeps only the last N turns.

    System messages are excluded from truncation and always
    preserved.

    Args:
        max_turns: Maximum number of messages to keep
            (excluding system messages).
    """

    max_turns: int

    def process(
        self, messages: list[Message]
    ) -> list[Message]:
        """Process messages by truncating to max_turns."""
        system_msgs = [
            m for m in messages
            if m.get('role') == 'system'
        ]
        non_system = [
            m for m in messages
            if m.get('role') != 'system'
        ]
        truncated = non_system[-self.max_turns:]
        return system_msgs + truncated


@dataclass(frozen=True, slots=True)
class SystemPromptStage:
    """Stage that inserts a system prompt at the beginning of
    the message list.

    Replaces existing system messages if present, otherwise
    adds one.

    Args:
        prompt: System prompt text to insert.
    """

    prompt: str

    def process(
        self, messages: list[Message]
    ) -> list[Message]:
        """Process messages by injecting system prompt."""
        filtered = [
            m for m in messages
            if m.get('role') != 'system'
        ]
        return [
            {'role': 'system', 'content': self.prompt}
        ] + filtered


@dataclass(frozen=True, slots=True)
class FilterByRoleStage:
    """Filter stage that keeps only messages with specific roles.

    Args:
        roles: Tuple of roles to keep
            (e.g., ('user', 'assistant')).
    """

    roles: tuple[str, ...] = ('user', 'assistant')

    def process(
        self, messages: list[Message]
    ) -> list[Message]:
        """Process messages by filtering to specified roles."""
        return [
            m for m in messages
            if m.get('role') in self.roles
        ]


@dataclass(frozen=True, slots=True)
class MetadataInjectionStage:
    """Stage that injects metadata into each message.

    Adds specified key-value pairs to message dictionaries.
    Does not overwrite existing keys.

    Args:
        metadata: Metadata dictionary to inject.
    """

    metadata: dict[str, str] = field(default_factory=dict)

    def process(
        self, messages: list[Message]
    ) -> list[Message]:
        """Process messages by injecting metadata."""
        result = []
        for msg in messages:
            enriched = dict(msg)
            for key, value in self.metadata.items():
                enriched.setdefault(key, value)
            result.append(enriched)
        return result
