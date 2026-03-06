"""ChatScreen - main TUI screen for Sonya CLI."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Input, Select, TextArea, Button
)

from sonya.cli.utils.chat_panel import ChatPanel
from sonya.cli.utils.settings_panel import SettingsPanel
from sonya.cli.client.agent_manager import AgentManager


class ChatScreen(Screen[None]):
    """Main screen containing the settings sidebar
    and the chat interface.
    """

    CSS = """
    ChatScreen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    SettingsPanel {
        width: 30%;
        min-width: 30;
        border-right: solid $boost;
    }

    ChatPanel {
        width: 70%;
    }
    """

    BINDINGS = [
        Binding(
            'ctrl+s', 'focus_settings',
            'Settings', show=True
        ),
        Binding(
            'ctrl+m', 'focus_chat',
            'Chat Input', show=True
        ),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_manager = AgentManager()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='main-container'):
            yield SettingsPanel(id='settings-panel')
            yield ChatPanel(id='chat-panel')
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Focus chat input by default
        self.action_focus_chat()

    def action_focus_settings(self) -> None:
        """Focus the settings panel."""
        self.query_one(SettingsPanel).focus_system_prompt()

    def action_focus_chat(self) -> None:
        """Focus the chat input."""
        self.query_one(ChatPanel).focus_input()

    async def on_input_submitted(
        self, event: Input.Submitted
    ) -> None:
        """Handle when the user hits Enter
        in the chat input.
        """
        if not event.value.strip():
            return

        user_msg = event.value
        event.input.value = ''

        chat_panel = self.query_one(ChatPanel)
        chat_panel.append_message('user', user_msg)

        # Read the current settings
        settings = self.query_one(SettingsPanel)
        model = settings.query_one(Select).value
        sys_prompt = settings.query_one(TextArea).text

        self.agent_manager.configure(
            str(model), sys_prompt
        )

        # Trigger the response generation in background
        self.generate_response(user_msg)

    @work(exclusive=True, thread=False)
    async def generate_response(
        self, user_msg: str
    ) -> None:
        """Run the LLM request in a worker task."""
        chat_panel = self.query_one(ChatPanel)

        try:
            log_widget = chat_panel.query_one('#chat-log')
            log_widget.write(
                '[blue bold]Assistant[/]: ',
                markup=True,
            )

            async for chunk in (
                self.agent_manager.chat_stream(user_msg)
            ):
                log_widget.write(chunk)

        except Exception as e:
            chat_panel.append_message(
                'system', f'ERROR: {str(e)}'
            )

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        """Handle button clicks (Reset)."""
        if event.button.id == 'reset-btn':
            self.agent_manager.reset()
            chat_panel = self.query_one(ChatPanel)
            log_widget = chat_panel.query_one('#chat-log')
            log_widget.clear()
            chat_panel.append_message(
                'system', 'Session Reset.'
            )
