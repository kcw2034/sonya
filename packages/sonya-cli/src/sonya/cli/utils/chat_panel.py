"""ChatPanel widget for Sonya CLI TUI."""

from rich.text import Text

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.timer import Timer
from textual.widgets import Input, Label, RichLog


class _PasteJoinInput(Input):
    """Input that joins multi-line pastes into a single line.

    The default Input._on_paste takes only the first line
    of pasted text, which truncates long API keys copied
    from websites that include line breaks.
    """

    def _on_paste(self, event: events.Paste) -> None:
        if event.text:
            text = ''.join(event.text.splitlines())
            selection = self.selection
            if selection.is_empty:
                self.insert_text_at_cursor(text)
            else:
                self.replace(text, *selection)
        event.stop()


_SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


class ThinkingIndicator(Label):
    """Animated spinner shown while waiting for LLM response."""

    CSS = """
    ThinkingIndicator {
        color: $text-muted;
        margin-left: 2;
        height: 1;
    }

    ThinkingIndicator.hidden {
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__('', **kwargs)
        self._frame: int = 0
        self._timer: Timer | None = None

    def show_spinner(self) -> None:
        """Start the spinner animation."""
        self._frame = 0
        self.remove_class('hidden')
        self._update_frame()
        self._timer = self.set_interval(
            0.08, self._update_frame
        )

    def hide_spinner(self) -> None:
        """Stop and hide the spinner."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.add_class('hidden')
        self.update('')

    def _update_frame(self) -> None:
        """Advance to the next spinner frame."""
        frame = _SPINNER_FRAMES[
            self._frame % len(_SPINNER_FRAMES)
        ]
        self.update(
            f'[cyan]{frame}[/] [dim]Thinking...[/]'
        )
        self._frame += 1


class ChatPanel(Vertical):
    """The main chat area."""

    CSS = """
    ChatPanel {
        layout: vertical;
        padding: 1;
    }

    #chat-log {
        height: 1fr;
        border: solid $accent;
    }

    #chat-input {
        dock: bottom;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(
            id='chat-log', highlight=True,
            wrap=True, markup=True,
        )
        yield ThinkingIndicator(
            id='thinking-indicator',
            classes='hidden',
        )
        yield _PasteJoinInput(
            placeholder='Type a message...',
            id='chat-input',
        )

    def focus_input(self) -> None:
        """Focus the input widget."""
        input_widget = self.query_one(
            '#chat-input', Input
        )
        input_widget.focus()

    def show_thinking(self) -> None:
        """Show the thinking spinner."""
        self.query_one(ThinkingIndicator).show_spinner()

    def hide_thinking(self) -> None:
        """Hide the thinking spinner."""
        self.query_one(ThinkingIndicator).hide_spinner()

    def append_message(
        self, role: str, content: str
    ) -> None:
        """Append a message to the chat log."""
        log = self.query_one('#chat-log', RichLog)
        _display_names = {
            'user': ('green', 'User'),
            'assistant': ('blue', 'Sonya'),
            'system': ('yellow', 'System'),
        }
        color, name = _display_names.get(
            role, ('white', role.capitalize())
        )
        line = Text()
        line.append(f'{name}: ', style=f'{color} bold')
        line.append(content)
        log.write(line)
