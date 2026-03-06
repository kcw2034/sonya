"""Sonya CLI entrypoint using Cyclopts."""

import sys
from cyclopts import App

app = App(name='sonya', help='Sonya Agent Framework CLI')

@app.command(name='chat')
def chat() -> None:
    """Launch the Sonya TUI chat interface."""
    from sonya.cli.client.app import SonyaTUI
    tui_app = SonyaTUI()
    tui_app.run()

if __name__ == '__main__':
    app()
