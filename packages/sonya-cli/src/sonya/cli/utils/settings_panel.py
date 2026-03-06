"""SettingsPanel widget for Sonya CLI TUI."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    Input, Select, TextArea, Label, Button
)


class SettingsPanel(Vertical):
    """The sidebar for agent settings."""

    CSS = """
    SettingsPanel {
        layout: vertical;
        padding: 1;
    }

    #setting-label {
        margin-top: 1;
        text-style: bold;
    }

    #model-select {
        margin-bottom: 1;
    }

    #system-prompt {
        height: 10;
        margin-bottom: 1;
    }

    #reset-btn {
        margin-top: 1;
        width: 100%;
        variant: primary;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label(
            'Instant Agent Settings',
            classes='setting-label',
        )

        yield Label('Model:', id='label-model')
        yield Select(
            (
                (
                    'Claude 3.5 Sonnet',
                    'claude-3-5-sonnet-20240620',
                ),
                ('GPT-4o', 'gpt-4o'),
                (
                    'Gemini 1.5 Flash',
                    'gemini-1.5-flash',
                ),
            ),
            id='model-select',
            allow_blank=False,
            value='claude-3-5-sonnet-20240620',
        )

        yield Label(
            'System Prompt:', id='label-prompt'
        )
        yield TextArea(
            'You are a helpful assistant.',
            id='system-prompt',
        )

        yield Button(
            'Reset Session', id='reset-btn'
        )

    def focus_system_prompt(self) -> None:
        """Focus the system prompt area."""
        prompt = self.query_one(
            '#system-prompt', TextArea
        )
        prompt.focus()
