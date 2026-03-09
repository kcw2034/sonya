"""Main Textual TUI application for Sonya CLI."""

import subprocess
import sys
import time
import socket

from dotenv import load_dotenv
from textual.app import App
from textual.binding import Binding

from sonya.cli.utils.chat_screen import ChatScreen

load_dotenv()

_GATEWAY_PORT = 8340


def _port_in_use(port: int) -> bool:
    """Check if a port is already listening."""
    with socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    ) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


class SonyaTUI(App[None]):
    """Main Textual Application for Sonya CLI."""

    TITLE = 'sonya'

    CSS = """
    Screen {
        background: $boost;
    }
    """

    BINDINGS = [
        Binding(
            'ctrl+c', 'quit', 'Quit', show=True
        ),
        Binding(
            'ctrl+d', 'toggle_dark',
            'Toggle Dark/Light', show=True
        ),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._gateway_proc: subprocess.Popen | None = (
            None
        )

    def on_mount(self) -> None:
        """Start gateway and install ChatScreen."""
        self._start_gateway()
        self.push_screen(ChatScreen())

    def _start_gateway(self) -> None:
        """Launch gateway server as subprocess."""
        if _port_in_use(_GATEWAY_PORT):
            return
        self._gateway_proc = subprocess.Popen(
            [
                sys.executable, '-m',
                'uvicorn',
                'sonya.gateway.server:app',
                '--host', '127.0.0.1',
                '--port', str(_GATEWAY_PORT),
                '--log-level', 'warning',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            if _port_in_use(_GATEWAY_PORT):
                break
            time.sleep(0.1)

    async def _on_exit_app(self) -> None:
        """Shutdown gateway on exit."""
        if self._gateway_proc is not None:
            self._gateway_proc.terminate()
            self._gateway_proc.wait(timeout=5)

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.theme = (
            'textual-light'
            if self.theme == 'textual-dark'
            else 'textual-dark'
        )


if __name__ == '__main__':
    app = SonyaTUI()
    app.run()
