from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, RichLog

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
        yield RichLog(id="chat-log", highlight=True, wrap=True)
        yield Input(placeholder="Type a message...", id="chat-input")

    def focus_input(self) -> None:
        """Focus the input widget."""
        input_widget = self.query_one("#chat-input", Input)
        input_widget.focus()

    def append_message(self, role: str, content: str) -> None:
        """Append a message to the chat log."""
        log = self.query_one("#chat-log", RichLog)
        color = "green" if role == "user" else "blue"
        # Using rich markup for display
        log.write(f"[{color} bold]{role.capitalize()}[/]: {content}")
