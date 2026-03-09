"""HTTP client for communicating with sonya-gateway."""

import json
from typing import Any, AsyncIterator

import httpx


class GatewayClient:
    """Async client for the Sonya Gateway REST + SSE API.

    Args:
        base_url: Gateway server URL.
    """

    def __init__(
        self, base_url: str = 'http://127.0.0.1:8340'
    ) -> None:
        self._base_url = base_url
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=120.0
        )
        self.session_id: str | None = None

    async def create_session(
        self,
        model: str,
        api_key: str,
        system_prompt: str = '',
    ) -> str:
        """Create a gateway session.

        Args:
            model: The model identifier.
            api_key: Provider API key.
            system_prompt: System instructions.

        Returns:
            The new session ID.
        """
        resp = await self._http.post(
            '/sessions',
            json={
                'model': model,
                'api_key': api_key,
                'system_prompt': system_prompt,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self.session_id = data['session_id']
        return self.session_id

    async def delete_session(self) -> None:
        """Delete the current session."""
        if self.session_id is None:
            return
        resp = await self._http.delete(
            f'/sessions/{self.session_id}'
        )
        resp.raise_for_status()
        self.session_id = None

    async def update_session(
        self,
        system_prompt: str | None = None,
    ) -> None:
        """Update the current session.

        Args:
            system_prompt: New system prompt.
        """
        if self.session_id is None:
            raise RuntimeError('No active session')
        body: dict[str, Any] = {}
        if system_prompt is not None:
            body['system_prompt'] = system_prompt
        resp = await self._http.patch(
            f'/sessions/{self.session_id}',
            json=body,
        )
        resp.raise_for_status()

    async def chat_stream(
        self, message: str
    ) -> AsyncIterator[str]:
        """Send a message and yield SSE chunks.

        Args:
            message: User message text.

        Yields:
            Text chunks from the LLM response.
        """
        if self.session_id is None:
            raise RuntimeError('No active session')

        async with self._http.stream(
            'POST',
            f'/sessions/{self.session_id}/chat',
            json={'message': message},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith('data:'):
                    raw = line[len('data:'):].strip()
                    if not raw:
                        continue
                    data = json.loads(raw)
                    if 'text' in data:
                        yield data['text']

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()
