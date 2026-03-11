"""In-memory session management for the gateway."""

import uuid
from typing import Any

from sonya.core import ClientConfig
from sonya.core.client.provider.anthropic import AnthropicClient
from sonya.core.client.provider.openai import OpenAIClient
from sonya.core.client.provider.google import GeminiClient
from sonya.core.parsers.adapter import get_adapter


def _create_provider_client(
    model: str, config: ClientConfig
) -> Any:
    """Instantiate the correct provider client.

    Args:
        model: The model identifier string.
        config: Pre-built client configuration.

    Returns:
        A provider client instance.
    """
    if model.startswith('claude'):
        return AnthropicClient(config)
    elif model.startswith('gpt'):
        return OpenAIClient(config)
    elif model.startswith('gemini'):
        return GeminiClient(config)
    else:
        return OpenAIClient(config)


class SessionManager:
    """Manages stateful LLM sessions in-memory.

    Each session holds a provider client, adapter,
    model config, system prompt, and conversation
    history.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create(
        self,
        model: str,
        api_key: str,
        system_prompt: str = '',
    ) -> str:
        """Create a new session.

        Args:
            model: The model identifier string.
            api_key: Provider API key.
            system_prompt: Optional system instructions.

        Returns:
            The new session ID.
        """
        config = ClientConfig(
            model=model, api_key=api_key
        )
        client = _create_provider_client(model, config)
        adapter = get_adapter(client)

        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = {
            'model': model,
            'client': client,
            'adapter': adapter,
            'system_prompt': system_prompt,
            'history': [],
        }
        return session_id

    def get(
        self, session_id: str
    ) -> dict[str, Any] | None:
        """Return session data or None.

        Args:
            session_id: The session ID to look up.

        Returns:
            Session dict or None if not found.
        """
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def update(
        self,
        session_id: str,
        system_prompt: str | None = None,
    ) -> bool:
        """Update session settings.

        Args:
            session_id: The session ID.
            system_prompt: New system prompt if provided.

        Returns:
            True if updated, False if not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if system_prompt is not None:
            session['system_prompt'] = system_prompt
        return True

    def list_all(self) -> list[dict[str, str | int]]:
        """Return summary of all sessions.

        Returns:
            List of session info dicts.
        """
        return [
            {
                'session_id': sid,
                'model': data['model'],
                'system_prompt': data['system_prompt'],
                'message_count': len(data['history']),
            }
            for sid, data in self._sessions.items()
        ]

    async def chat_stream(
        self, session_id: str, message: str
    ) -> Any:
        """Send a message and yield response chunks.

        Args:
            session_id: The session ID.
            message: User message text.

        Yields:
            String chunks of the LLM response.

        Raises:
            KeyError: If session not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(
                f'Session not found: {session_id}'
            )

        client = session['client']
        adapter = session['adapter']
        history = session['history']

        history.append(
            {'role': 'user', 'content': message}
        )

        gen_kwargs = adapter.format_generate_kwargs(
            session['system_prompt'], None
        )
        messages = adapter.format_messages(
            history.copy()
        )

        full_response = ''
        try:
            async for chunk in client.generate_stream(
                messages=messages, **gen_kwargs
            ):
                full_response += chunk
                yield chunk
        finally:
            history.append(
                {
                    'role': 'assistant',
                    'content': full_response,
                }
            )
