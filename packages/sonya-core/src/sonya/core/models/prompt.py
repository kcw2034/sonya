"""Structured prompt types for agent instructions."""

from __future__ import annotations

from dataclasses import dataclass


class _SafeDict(dict):
    """Dict subclass that preserves missing keys as-is.

    When used with ``str.format_map``, missing keys are
    returned as ``{key}`` instead of raising KeyError.
    """

    def __missing__(self, key: str) -> str:
        return '{' + key + '}'


@dataclass(frozen=True, slots=True)
class Example:
    """Few-shot example pair.

    Args:
        user: User message content.
        assistant: Expected assistant response.
    """

    user: str
    assistant: str


@dataclass(frozen=True, slots=True)
class Prompt:
    """Structured prompt with named sections.

    Sections are rendered in order: role, guidelines,
    constraints, examples, output_format. Empty sections
    are skipped. Template variables use ``{placeholder}``
    syntax, substituted via ``render(**context)``.

    Args:
        role: Agent identity and expertise scope.
        guidelines: Behavioral rules (do this).
        constraints: Restrictions (don't do this).
        examples: Few-shot example pairs.
        output_format: Expected response structure.

    Example::

        prompt = Prompt(
            role='You are a {domain} expert.',
            guidelines=('Use tools first.',),
            constraints=('Never fabricate data.',),
            examples=(
                Example(user='Hello', assistant='Hi!'),
            ),
            output_format='Respond in JSON.',
        )
        text = prompt.render(domain='weather')
    """

    role: str = ''
    guidelines: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    examples: tuple[Example, ...] = ()
    output_format: str = ''

    def render(self, **context: str) -> str:
        """Render prompt to final string.

        Assembles non-empty sections in order and
        substitutes ``{placeholder}`` variables from
        *context*. Missing variables are left as-is.

        Args:
            **context: Template variable substitutions.

        Returns:
            Rendered prompt string.
        """
        sections: list[str] = []

        if self.role:
            sections.append(self.role)

        if self.guidelines:
            lines = '\n'.join(
                f'- {g}' for g in self.guidelines
            )
            sections.append(f'## Guidelines\n{lines}')

        if self.constraints:
            lines = '\n'.join(
                f'- {c}' for c in self.constraints
            )
            sections.append(f'## Constraints\n{lines}')

        if self.examples:
            parts: list[str] = []
            for ex in self.examples:
                parts.append(
                    f'User: {ex.user}\n'
                    f'Assistant: {ex.assistant}'
                )
            body = '\n\n'.join(parts)
            sections.append(f'## Examples\n\n{body}')

        if self.output_format:
            sections.append(
                f'## Output Format\n{self.output_format}'
            )

        text = '\n\n'.join(sections)

        if context:
            text = text.format_map(_SafeDict(context))

        return text

    @staticmethod
    def from_str(text: str) -> Prompt:
        """Create a Prompt with the given text as role.

        Args:
            text: Plain text to use as the role section.

        Returns:
            A new Prompt instance.
        """
        return Prompt(role=text)
