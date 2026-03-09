"""ChatScreen - main TUI screen for Sonya CLI."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Input, Select, TextArea, Button
)

from sonya.cli.utils.auth import (
    check_api_key,
    get_provider_by_model,
    save_api_key,
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
        self._awaiting_api_key: dict[str, str] | None = None

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

        value = event.value.strip()
        event.input.value = ''
        chat_panel = self.query_one(ChatPanel)

        # Handle API key input mode
        if self._awaiting_api_key is not None:
            self._handle_api_key_input(value)
            return

        chat_panel.append_message('user', value)

        # Read the current settings
        settings = self.query_one(SettingsPanel)
        model = str(settings.query_one(Select).value)
        sys_prompt = settings.query_one(TextArea).text

        # Check API key before calling
        if not check_api_key(model):
            self._prompt_api_key(model)
            return

        self.agent_manager.configure(model, sys_prompt)

        # Trigger the response generation in background
        self.generate_response(value)

    def _prompt_api_key(self, model: str) -> None:
        """Show API key setup prompt in the chat log."""
        provider = get_provider_by_model(model)
        if provider is None:
            return

        chat_panel = self.query_one(ChatPanel)
        chat_panel.append_message(
            'system',
            f'{provider["name"]} API key is not set.\n'
            f'Get your key at: {provider["url"]}\n'
            f'Paste your API key below and press Enter.'
        )

        input_widget = chat_panel.query_one(
            '#chat-input', Input
        )
        input_widget.placeholder = (
            f'Enter {provider["name"]} API key...'
        )
        self._awaiting_api_key = provider

    def _handle_api_key_input(
        self, api_key: str
    ) -> None:
        """Process the API key entered by the user."""
        provider = self._awaiting_api_key
        self._awaiting_api_key = None

        chat_panel = self.query_one(ChatPanel)
        input_widget = chat_panel.query_one(
            '#chat-input', Input
        )
        input_widget.placeholder = 'Type a message...'

        if not api_key:
            chat_panel.append_message(
                'system', 'API key setup cancelled.'
            )
            return

        save_api_key(provider['env_key'], api_key)
        chat_panel.append_message(
            'system',
            f'{provider["name"]} API key saved. '
            f'You can now chat with this model.'
        )

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
