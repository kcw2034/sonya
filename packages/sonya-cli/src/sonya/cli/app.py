import os
from typing import TextIO

from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from sonya.cli.screens.chat import ChatScreen

# Load environment variables (e.g., API keys) from .env
load_dotenv()

class SonyaTUI(App[None]):
    """Main Textual Application for Sonya CLI."""

    CSS = """
    Screen {
        background: $boost;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+d", "toggle_dark", "Toggle Dark/Light", show=True),
    ]

    def on_mount(self) -> None:
        """Call when app starts. Install the main ChatScreen."""
        self.push_screen(ChatScreen())

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

if __name__ == "__main__":
    app = SonyaTUI()
    app.run()
