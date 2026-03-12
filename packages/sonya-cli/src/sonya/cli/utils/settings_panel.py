"""SettingsPanel widget for Sonya CLI TUI."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    Select, TextArea, Label, Button
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
                    'Claude 4.6 Sonnet',
                    'claude-sonnet-4-6',
                ),
                (
                    'Claude 4.5 Haiku',
                    'claude-haiku-4-5-20251001',
                ),
                ('GPT-4o', 'gpt-4o'),
                (
                    'GPT-4.1',
                    'gpt-4.1',
                ),
                (
                    'GPT-4.1 mini',
                    'gpt-4.1-mini',
                ),
                (
                    'Gemini 3 Flash Preview',
                    'gemini-3-flash-preview',
                ),
                (
                    'Gemini 3.1 Pro Preview',
                    'gemini-3.1-pro-preview',
                ),
            ),
            id='model-select',
            allow_blank=False,
            value='claude-sonnet-4-6',
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
