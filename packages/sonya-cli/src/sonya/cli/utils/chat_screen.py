"""ChatScreen - main TUI screen for Sonya CLI."""

import json
import os

import httpx
from rich.text import Text

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Input, RichLog,
    Select, TextArea, Button,
)

from sonya.cli.utils.auth import (
    check_api_key,
    get_provider_by_model,
    save_api_key,
)
from sonya.cli.utils.chat_panel import ChatPanel
from sonya.cli.utils.settings_panel import SettingsPanel
from sonya.cli.client.gateway_client import GatewayClient


class ChatScreen(Screen[None]):
    """Main screen with settings sidebar and chat."""

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
            'ctrl+b', 'focus_settings',
            'Settings', show=True
        ),
        Binding(
            'ctrl+n', 'focus_chat',
            'Chat Input', show=True
        ),
        Binding(
            'ctrl+y', 'copy_last',
            'Copy Last', show=True
        ),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._gateway = GatewayClient()
        self._current_model: str = ''
        self._last_response: str = ''
        self._awaiting_api_key: (
            dict[str, str] | None
        ) = None
        self._pending_message: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='main-container'):
            yield SettingsPanel(id='settings-panel')
            yield ChatPanel(id='chat-panel')
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.action_focus_chat()

    def action_focus_settings(self) -> None:
        """Focus the settings panel."""
        self.query_one(
            SettingsPanel
        ).focus_system_prompt()

    def action_focus_chat(self) -> None:
        """Focus the chat input."""
        self.query_one(ChatPanel).focus_input()

    async def on_input_submitted(
        self, event: Input.Submitted
    ) -> None:
        """Handle when the user hits Enter."""
        if not event.value.strip():
            return

        value = event.value.strip()
        event.input.value = ''
        chat_panel = self.query_one(ChatPanel)

        if self._awaiting_api_key is not None:
            self._handle_api_key_input(value)
            return

        chat_panel.append_message('user', value)

        settings = self.query_one(SettingsPanel)
        model = str(settings.query_one(Select).value)
        sys_prompt = settings.query_one(TextArea).text

        if not check_api_key(model):
            self._pending_message = value
            self._prompt_api_key(model)
            return

        await self._ensure_session(model, sys_prompt)
        self.generate_response(value)

    async def _ensure_session(
        self, model: str, system_prompt: str
    ) -> None:
        """Create or update the gateway session."""
        if (
            self._gateway.session_id is None
            or self._current_model != model
        ):
            provider = get_provider_by_model(model)
            api_key = os.environ.get(
                provider['env_key'], ''
            ) if provider else ''

            if self._gateway.session_id is not None:
                await self._gateway.delete_session()

            await self._gateway.create_session(
                model=model,
                api_key=api_key,
                system_prompt=system_prompt,
            )
            self._current_model = model
        else:
            await self._gateway.update_session(
                system_prompt=system_prompt,
            )

    def _prompt_api_key(self, model: str) -> None:
        """Show API key setup prompt."""
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

        if self._pending_message:
            pending = self._pending_message
            self._pending_message = None

            settings = self.query_one(SettingsPanel)
            model = str(
                settings.query_one(Select).value
            )
            sys_prompt = (
                settings.query_one(TextArea).text
            )
            self._ensure_and_send(
                model, sys_prompt, api_key, pending
            )

    @work(exclusive=True, thread=False)
    async def _ensure_and_send(
        self,
        model: str,
        sys_prompt: str,
        api_key: str,
        message: str,
    ) -> None:
        """Create session with new key and send."""
        if self._gateway.session_id is not None:
            await self._gateway.delete_session()

        await self._gateway.create_session(
            model=model,
            api_key=api_key,
            system_prompt=sys_prompt,
        )
        self._current_model = model
        await self._do_generate(message)

    @work(exclusive=True, thread=False)
    async def generate_response(
        self, user_msg: str
    ) -> None:
        """Run the LLM request in a worker task."""
        await self._do_generate(user_msg)

    async def _do_generate(
        self, user_msg: str
    ) -> None:
        """Shared streaming logic."""
        chat_panel = self.query_one(ChatPanel)
        chat_panel.show_thinking()
        self._stream_line_count = 0

        try:
            log_widget = chat_panel.query_one(
                '#chat-log', RichLog
            )
            buffer = ''
            first_chunk = True

            async for chunk in (
                self._gateway.chat_stream(user_msg)
            ):
                if first_chunk:
                    chat_panel.hide_thinking()
                    first_chunk = False

                buffer += chunk
                self._render_stream(
                    log_widget, buffer
                )

            if first_chunk:
                chat_panel.hide_thinking()

            self._last_response = buffer

        except (
            RuntimeError,
            httpx.HTTPStatusError,
            httpx.ConnectError,
            json.JSONDecodeError,
        ) as e:
            # RuntimeError: no active session
            # httpx errors: network or HTTP-level failures
            # JSONDecodeError: malformed SSE payload
            chat_panel.hide_thinking()
            chat_panel.append_message(
                'system', f'ERROR: {str(e)}'
            )

    def _render_stream(
        self, log_widget: RichLog, text: str
    ) -> None:
        """Re-render the streaming assistant message."""
        count = getattr(self, '_stream_line_count', 0)
        if count > 0:
            del log_widget.lines[-count:]
            from textual.geometry import Size
            log_widget.virtual_size = Size(
                log_widget.virtual_size.width,
                len(log_widget.lines),
            )

        before = len(log_widget.lines)
        line = Text()
        line.append('Sonya: ', style='blue bold')
        line.append(text)
        log_widget.write(line)
        self._stream_line_count = (
            len(log_widget.lines) - before
        )

    def action_copy_last(self) -> None:
        """Copy the last assistant response."""
        if not self._last_response:
            return

        self.app.copy_to_clipboard(
            self._last_response
        )
        chat_panel = self.query_one(ChatPanel)
        chat_panel.append_message(
            'system',
            'Last response copied to clipboard.'
        )

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        """Handle button clicks (Reset)."""
        if event.button.id == 'reset-btn':
            self._reset_session()

    @work(exclusive=True, thread=False)
    async def _reset_session(self) -> None:
        """Delete gateway session and clear UI."""
        if self._gateway.session_id is not None:
            await self._gateway.delete_session()
        self._current_model = ''
        self._last_response = ''
        chat_panel = self.query_one(ChatPanel)
        log_widget = chat_panel.query_one('#chat-log')
        log_widget.clear()
        chat_panel.append_message(
            'system', 'Session Reset.'
        )
