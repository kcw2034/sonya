"""Background worker for interacting with sonya.core Agents."""

import asyncio
from typing import Any

from sonya.core import Agent, ClientConfig
from sonya.core.client.provider.anthropic import AnthropicClient
from sonya.core.client.provider.openai import OpenAIClient
from sonya.core.client.provider.google import GeminiClient


def create_client(model: str) -> Any:
    """Helper to instantiate the correct client
    based on the model string.
    """
    config = ClientConfig(model=model)
    if model.startswith('claude'):
        return AnthropicClient(config)
    elif model.startswith('gpt'):
        return OpenAIClient(config)
    elif model.startswith('gemini'):
        return GeminiClient(config)
    else:
        # Fallback to OpenAI if unknown
        return OpenAIClient(config)


class AgentManager:
    """Manages the Instant Agent lifecycle and history."""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []
        self.system_prompt: str = ''
        self.model: str = 'claude-3-5-sonnet-20240620'
        self._client: Any = None
        self._agent: Agent | None = None

    def reset(self) -> None:
        """Clear conversation history."""
        self.history = []

    def configure(
        self, model: str, system_prompt: str
    ) -> None:
        """Update agent configuration."""
        self.model = model
        self.system_prompt = system_prompt
        self._client = create_client(self.model)
        self._agent = Agent(
            name='InstantAgent',
            client=self._client,
            instructions=self.system_prompt,
        )

    async def chat_stream(
        self, user_message: str
    ) -> Any:
        """Send a message to the agent and yield
        the streaming response chunks.
        """
        if not self._agent:
            self.configure(self.model, self.system_prompt)

        self.history.append(
            {'role': 'user', 'content': user_message}
        )

        # NOTE: Using the raw client stream for now
        # until Agent has stream support.
        messages = self.history.copy()
        if self._agent.instructions:
            messages.insert(
                0,
                {
                    'role': 'system',
                    'content': self._agent.instructions,
                },
            )

        full_response = ''
        try:
            async for chunk in self._client.generate_stream(
                messages=messages
            ):
                full_response += chunk
                yield chunk
        finally:
            self.history.append(
                {
                    'role': 'assistant',
                    'content': full_response,
                }
            )
