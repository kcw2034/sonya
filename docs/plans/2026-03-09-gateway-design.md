# Sonya Gateway Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create `sonya-gateway` package — a REST + SSE server that sits between UI clients (TUI, GUI, Discord/Slack) and `sonya-core`.

**Architecture:** FastAPI server manages stateful sessions in-memory. Each session binds a model, API key, client, adapter, and conversation history. Clients POST messages and receive SSE-streamed responses. TUI launches the gateway as a subprocess and communicates via httpx.

**Tech Stack:** FastAPI, uvicorn, sse-starlette, httpx (TUI client side), sonya-core

---

### Task 1: Create sonya-gateway package scaffold

**Files:**
- Create: `packages/sonya-gateway/pyproject.toml`
- Create: `packages/sonya-gateway/src/sonya/gateway/__init__.py`
- Create: `packages/sonya-gateway/tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p packages/sonya-gateway/src/sonya/gateway
mkdir -p packages/sonya-gateway/tests
```

**Step 2: Write pyproject.toml**

Create `packages/sonya-gateway/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sonya-gateway"
version = "0.0.1"
description = "Local REST + SSE gateway for Sonya agents"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    {name = "Sonya Contributors"},
]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.0",
    "sonya-core",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "httpx>=0.27"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"

[tool.uv.sources]
sonya-core = { path = "../sonya-core", editable = true }
```

**Step 3: Write `__init__.py` files**

`packages/sonya-gateway/src/sonya/gateway/__init__.py`:
```python
"""Sonya Gateway — REST + SSE server for LLM sessions."""
```

`packages/sonya-gateway/tests/__init__.py`: empty file.

**Step 4: Install the package**

```bash
cd /Users/kimchan-woo/Desktop/kcw-workspace/sonya
uv pip install -e packages/sonya-gateway
```

**Step 5: Verify import**

```bash
python -c "import sonya.gateway; print('OK')"
```

**Step 6: Commit**

```bash
git add packages/sonya-gateway/
git commit -m "feat(sonya-gateway): scaffold package"
```

---

### Task 2: Implement schemas (Pydantic models)

**Files:**
- Create: `packages/sonya-gateway/src/sonya/gateway/schemas.py`
- Create: `packages/sonya-gateway/tests/test_schemas.py`

**Step 1: Write the failing test**

`packages/sonya-gateway/tests/test_schemas.py`:

```python
"""Tests for gateway request/response schemas."""

from sonya.gateway.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    UpdateSessionRequest,
    ChatRequest,
    SessionInfo,
)


class TestCreateSessionRequest:

    def test_required_fields(self) -> None:
        req = CreateSessionRequest(
            model='claude-sonnet-4-6',
            api_key='sk-test-123',
        )
        assert req.model == 'claude-sonnet-4-6'
        assert req.api_key == 'sk-test-123'
        assert req.system_prompt == ''

    def test_optional_system_prompt(self) -> None:
        req = CreateSessionRequest(
            model='gpt-4o',
            api_key='sk-test',
            system_prompt='Be helpful.',
        )
        assert req.system_prompt == 'Be helpful.'


class TestCreateSessionResponse:

    def test_fields(self) -> None:
        resp = CreateSessionResponse(
            session_id='abc-123',
            model='claude-sonnet-4-6',
        )
        assert resp.session_id == 'abc-123'


class TestUpdateSessionRequest:

    def test_all_optional(self) -> None:
        req = UpdateSessionRequest()
        assert req.system_prompt is None

    def test_with_prompt(self) -> None:
        req = UpdateSessionRequest(
            system_prompt='New prompt'
        )
        assert req.system_prompt == 'New prompt'


class TestChatRequest:

    def test_message_field(self) -> None:
        req = ChatRequest(message='hello')
        assert req.message == 'hello'


class TestSessionInfo:

    def test_fields(self) -> None:
        info = SessionInfo(
            session_id='abc',
            model='claude-sonnet-4-6',
            system_prompt='test',
            message_count=5,
        )
        assert info.message_count == 5
```

**Step 2: Run test to verify it fails**

```bash
pytest packages/sonya-gateway/tests/test_schemas.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sonya.gateway.schemas'`

**Step 3: Write the implementation**

`packages/sonya-gateway/src/sonya/gateway/schemas.py`:

```python
"""Request and response schemas for the gateway API."""

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    """Request body for POST /sessions."""

    model: str
    api_key: str
    system_prompt: str = ''


class CreateSessionResponse(BaseModel):
    """Response body for POST /sessions."""

    session_id: str
    model: str


class UpdateSessionRequest(BaseModel):
    """Request body for PATCH /sessions/{id}."""

    system_prompt: str | None = None


class ChatRequest(BaseModel):
    """Request body for POST /sessions/{id}/chat."""

    message: str


class SessionInfo(BaseModel):
    """Response body for GET /sessions/{id}."""

    session_id: str
    model: str
    system_prompt: str
    message_count: int
```

**Step 4: Run test to verify it passes**

```bash
pytest packages/sonya-gateway/tests/test_schemas.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/schemas.py packages/sonya-gateway/tests/test_schemas.py
git commit -m "feat(sonya-gateway): add request/response schemas"
```

---

### Task 3: Implement SessionManager

**Files:**
- Create: `packages/sonya-gateway/src/sonya/gateway/session.py`
- Create: `packages/sonya-gateway/tests/test_session.py`

**Step 1: Write the failing test**

`packages/sonya-gateway/tests/test_session.py`:

```python
"""Tests for gateway SessionManager."""

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from sonya.gateway.session import SessionManager


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager()


class TestSessionLifecycle:

    def test_create_session(self, manager: SessionManager) -> None:
        with patch(
            'sonya.gateway.session._create_provider_client'
        ) as mock_client, patch(
            'sonya.gateway.session._get_adapter'
        ) as mock_adapter:
            mock_client.return_value = MagicMock()
            mock_adapter.return_value = MagicMock()

            sid = manager.create(
                model='claude-sonnet-4-6',
                api_key='sk-test',
                system_prompt='Be helpful.',
            )

            assert sid in manager._sessions
            session = manager._sessions[sid]
            assert session['model'] == 'claude-sonnet-4-6'
            assert session['system_prompt'] == 'Be helpful.'
            assert session['history'] == []

    def test_get_session(self, manager: SessionManager) -> None:
        with patch(
            'sonya.gateway.session._create_provider_client'
        ), patch(
            'sonya.gateway.session._get_adapter'
        ):
            sid = manager.create(
                model='gpt-4o',
                api_key='sk-test',
            )
            session = manager.get(sid)
            assert session is not None
            assert session['model'] == 'gpt-4o'

    def test_get_unknown_returns_none(
        self, manager: SessionManager
    ) -> None:
        assert manager.get('nonexistent') is None

    def test_delete_session(self, manager: SessionManager) -> None:
        with patch(
            'sonya.gateway.session._create_provider_client'
        ), patch(
            'sonya.gateway.session._get_adapter'
        ):
            sid = manager.create(
                model='claude-sonnet-4-6',
                api_key='sk-test',
            )
            deleted = manager.delete(sid)
            assert deleted is True
            assert manager.get(sid) is None

    def test_delete_unknown_returns_false(
        self, manager: SessionManager
    ) -> None:
        assert manager.delete('nonexistent') is False

    def test_update_system_prompt(
        self, manager: SessionManager
    ) -> None:
        with patch(
            'sonya.gateway.session._create_provider_client'
        ), patch(
            'sonya.gateway.session._get_adapter'
        ):
            sid = manager.create(
                model='claude-sonnet-4-6',
                api_key='sk-test',
                system_prompt='old',
            )
            manager.update(sid, system_prompt='new')
            session = manager.get(sid)
            assert session['system_prompt'] == 'new'
```

**Step 2: Run test to verify it fails**

```bash
pytest packages/sonya-gateway/tests/test_session.py -v
```
Expected: FAIL

**Step 3: Write the implementation**

`packages/sonya-gateway/src/sonya/gateway/session.py`:

```python
"""In-memory session management for the gateway."""

import uuid
from typing import Any

from sonya.core import ClientConfig
from sonya.core.client.provider.anthropic import AnthropicClient
from sonya.core.client.provider.openai import OpenAIClient
from sonya.core.client.provider.google import GeminiClient
from sonya.core.parsers.adapter import _get_adapter


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
        adapter = _get_adapter(client)

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
```

**Step 4: Run test to verify it passes**

```bash
pytest packages/sonya-gateway/tests/test_session.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/session.py packages/sonya-gateway/tests/test_session.py
git commit -m "feat(sonya-gateway): add SessionManager"
```

---

### Task 4: Implement FastAPI server with SSE

**Files:**
- Create: `packages/sonya-gateway/src/sonya/gateway/server.py`
- Create: `packages/sonya-gateway/tests/test_server.py`

**Step 1: Write the failing test**

`packages/sonya-gateway/tests/test_server.py`:

```python
"""Tests for gateway FastAPI server."""

import json
import pytest

from unittest.mock import patch, MagicMock, AsyncMock

from httpx import AsyncClient, ASGITransport

from sonya.gateway.server import app


@pytest.fixture
def mock_session_manager():
    with patch(
        'sonya.gateway.server.session_manager'
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_create_session(
    mock_session_manager,
) -> None:
    mock_session_manager.create.return_value = 'abc123'

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.post(
            '/sessions',
            json={
                'model': 'claude-sonnet-4-6',
                'api_key': 'sk-test',
                'system_prompt': 'Be helpful.',
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data['session_id'] == 'abc123'
    assert data['model'] == 'claude-sonnet-4-6'


@pytest.mark.asyncio
async def test_delete_session(
    mock_session_manager,
) -> None:
    mock_session_manager.delete.return_value = True

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.delete('/sessions/abc123')

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_session_not_found(
    mock_session_manager,
) -> None:
    mock_session_manager.delete.return_value = False

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.delete('/sessions/unknown')

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_session(
    mock_session_manager,
) -> None:
    mock_session_manager.update.return_value = True

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.patch(
            '/sessions/abc123',
            json={'system_prompt': 'New prompt'},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_session_not_found(
    mock_session_manager,
) -> None:
    mock_session_manager.update.return_value = False

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.patch(
            '/sessions/unknown',
            json={'system_prompt': 'test'},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_stream_session_not_found(
    mock_session_manager,
) -> None:
    mock_session_manager.get.return_value = None

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.post(
            '/sessions/unknown/chat',
            json={'message': 'hello'},
        )

    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

```bash
pytest packages/sonya-gateway/tests/test_server.py -v
```
Expected: FAIL

**Step 3: Write the implementation**

`packages/sonya-gateway/src/sonya/gateway/server.py`:

```python
"""FastAPI server for the Sonya Gateway."""

import json
from typing import AsyncGenerator

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from sonya.gateway.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    UpdateSessionRequest,
    ChatRequest,
    SessionInfo,
)
from sonya.gateway.session import SessionManager

app = FastAPI(title='Sonya Gateway')
session_manager = SessionManager()


@app.post(
    '/sessions',
    response_model=CreateSessionResponse,
    status_code=201,
)
async def create_session(
    body: CreateSessionRequest,
) -> CreateSessionResponse:
    """Create a new LLM session."""
    session_id = session_manager.create(
        model=body.model,
        api_key=body.api_key,
        system_prompt=body.system_prompt,
    )
    return CreateSessionResponse(
        session_id=session_id,
        model=body.model,
    )


@app.delete('/sessions/{session_id}', status_code=204)
async def delete_session(session_id: str) -> Response:
    """Delete a session."""
    if not session_manager.delete(session_id):
        return JSONResponse(
            status_code=404,
            content={'detail': 'Session not found'},
        )
    return Response(status_code=204)


@app.patch('/sessions/{session_id}')
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
) -> dict:
    """Update session settings."""
    if not session_manager.update(
        session_id,
        system_prompt=body.system_prompt,
    ):
        return JSONResponse(
            status_code=404,
            content={'detail': 'Session not found'},
        )
    return {'status': 'updated'}


@app.post('/sessions/{session_id}/chat')
async def chat(
    session_id: str, body: ChatRequest
) -> EventSourceResponse:
    """Stream a chat response via SSE."""
    session = session_manager.get(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={'detail': 'Session not found'},
        )

    async def _stream() -> AsyncGenerator[dict, None]:
        full_text = ''
        try:
            async for chunk in (
                session_manager.chat_stream(
                    session_id, body.message
                )
            ):
                full_text += chunk
                yield {
                    'event': 'chunk',
                    'data': json.dumps(
                        {'text': chunk}
                    ),
                }
            yield {
                'event': 'done',
                'data': json.dumps(
                    {'full_text': full_text}
                ),
            }
        except Exception as e:
            yield {
                'event': 'error',
                'data': json.dumps(
                    {'message': str(e)}
                ),
            }

    return EventSourceResponse(_stream())
```

**Step 4: Run test to verify it passes**

```bash
pytest packages/sonya-gateway/tests/test_server.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/server.py packages/sonya-gateway/tests/test_server.py
git commit -m "feat(sonya-gateway): add FastAPI server with SSE"
```

---

### Task 5: Add gateway CLI entrypoint

**Files:**
- Modify: `packages/sonya-gateway/pyproject.toml`
- Modify: `packages/sonya-gateway/src/sonya/gateway/__init__.py`

**Step 1: Add console_scripts to pyproject.toml**

In `pyproject.toml`, add after `[project.optional-dependencies]`:

```toml
[project.scripts]
sonya-gateway = "sonya.gateway:run_server"
```

**Step 2: Update `__init__.py` with run_server**

```python
"""Sonya Gateway — REST + SSE server for LLM sessions."""

import uvicorn


def run_server(
    host: str = '127.0.0.1',
    port: int = 8340,
) -> None:
    """Start the gateway server.

    Args:
        host: Bind address.
        port: Bind port.
    """
    uvicorn.run(
        'sonya.gateway.server:app',
        host=host,
        port=port,
    )
```

**Step 3: Reinstall and verify**

```bash
uv pip install -e packages/sonya-gateway
sonya-gateway &
curl http://127.0.0.1:8340/docs
kill %1
```

**Step 4: Commit**

```bash
git add packages/sonya-gateway/
git commit -m "feat(sonya-gateway): add CLI entrypoint"
```

---

### Task 6: Add GatewayClient to sonya-cli

**Files:**
- Create: `packages/sonya-cli/src/sonya/cli/client/gateway_client.py`
- Create: `packages/sonya-cli/tests/test_gateway_client.py`
- Modify: `packages/sonya-cli/pyproject.toml` (add httpx dependency)

**Step 1: Add httpx to sonya-cli dependencies**

In `packages/sonya-cli/pyproject.toml`, add `"httpx>=0.27"` to dependencies.

**Step 2: Write the failing test**

`packages/sonya-cli/tests/test_gateway_client.py`:

```python
"""Tests for GatewayClient."""

import json
import pytest

from unittest.mock import AsyncMock, patch, MagicMock

from sonya.cli.client.gateway_client import GatewayClient


class TestGatewayClient:

    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        client = GatewayClient(base_url='http://test')

        mock_resp = AsyncMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            'session_id': 'abc123',
            'model': 'claude-sonnet-4-6',
        }

        with patch.object(
            client._http, 'post',
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            result = await client.create_session(
                model='claude-sonnet-4-6',
                api_key='sk-test',
                system_prompt='Be helpful.',
            )

        assert result == 'abc123'
        assert client.session_id == 'abc123'

    @pytest.mark.asyncio
    async def test_delete_session(self) -> None:
        client = GatewayClient(base_url='http://test')
        client.session_id = 'abc123'

        mock_resp = AsyncMock()
        mock_resp.status_code = 204

        with patch.object(
            client._http, 'delete',
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            await client.delete_session()

        assert client.session_id is None

    @pytest.mark.asyncio
    async def test_update_session(self) -> None:
        client = GatewayClient(base_url='http://test')
        client.session_id = 'abc123'

        mock_resp = AsyncMock()
        mock_resp.status_code = 200

        with patch.object(
            client._http, 'patch',
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            await client.update_session(
                system_prompt='New prompt'
            )
```

**Step 3: Run test to verify it fails**

```bash
pytest packages/sonya-cli/tests/test_gateway_client.py -v
```

**Step 4: Write the implementation**

`packages/sonya-cli/src/sonya/cli/client/gateway_client.py`:

```python
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
```

**Step 5: Run test to verify it passes**

```bash
pytest packages/sonya-cli/tests/test_gateway_client.py -v
```

**Step 6: Commit**

```bash
git add packages/sonya-cli/
git commit -m "feat(sonya-cli): add GatewayClient for gateway communication"
```

---

### Task 7: Wire TUI to use GatewayClient instead of AgentManager

**Files:**
- Modify: `packages/sonya-cli/src/sonya/cli/client/app.py`
- Modify: `packages/sonya-cli/src/sonya/cli/utils/chat_screen.py`
- Modify: `packages/sonya-cli/src/sonya/cli/client/cli.py`

**Step 1: Update app.py — launch gateway subprocess on start**

`packages/sonya-cli/src/sonya/cli/client/app.py`:

```python
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
        self._gateway_proc: subprocess.Popen | None = None

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
        # Wait for server to be ready
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
```

**Step 2: Rewrite chat_screen.py — replace AgentManager with GatewayClient**

Replace `AgentManager` usage with `GatewayClient`. Key changes:
- `self.agent_manager` → `self._gateway`  (a `GatewayClient` instance)
- `open_session()` + `configure()` → `create_session()` or `update_session()`
- `chat_stream()` now consumes SSE via httpx
- `history` is server-side; `action_copy_last` tracks last response locally

`packages/sonya-cli/src/sonya/cli/utils/chat_screen.py`:

```python
"""ChatScreen - main TUI screen for Sonya CLI."""

import os

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
        self.action_focus_chat()

    def action_focus_settings(self) -> None:
        self.query_one(
            SettingsPanel
        ).focus_system_prompt()

    def action_focus_chat(self) -> None:
        self.query_one(ChatPanel).focus_input()

    async def on_input_submitted(
        self, event: Input.Submitted
    ) -> None:
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

        except Exception as e:
            chat_panel.hide_thinking()
            chat_panel.append_message(
                'system', f'ERROR: {str(e)}'
            )

    def _render_stream(
        self, log_widget: RichLog, text: str
    ) -> None:
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
        if not self._last_response:
            return

        self.app.copy_to_clipboard(self._last_response)
        chat_panel = self.query_one(ChatPanel)
        chat_panel.append_message(
            'system', 'Last response copied to clipboard.'
        )

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        if event.button.id == 'reset-btn':
            self._reset_session()

    @work(exclusive=True, thread=False)
    async def _reset_session(self) -> None:
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
```

**Step 3: Verify imports**

```bash
python -c "from sonya.cli.utils.chat_screen import ChatScreen; print('OK')"
```

**Step 4: Run all tests**

```bash
pytest packages/sonya-gateway/tests/ packages/sonya-cli/tests/ -v
```

**Step 5: Commit**

```bash
git add packages/sonya-cli/
git commit -m "refactor(sonya-cli): wire TUI to gateway via GatewayClient"
```

---

### Task 8: Clean up old AgentManager

**Files:**
- Delete: `packages/sonya-cli/src/sonya/cli/client/agent_manager.py`

**Step 1: Verify no remaining imports**

```bash
grep -r 'agent_manager' packages/sonya-cli/src/
```
Expected: no results

**Step 2: Delete the file**

```bash
rm packages/sonya-cli/src/sonya/cli/client/agent_manager.py
```

**Step 3: Run all tests**

```bash
pytest packages/sonya-gateway/tests/ packages/sonya-cli/tests/ packages/sonya-core/tests/ -v
```

**Step 4: Commit**

```bash
git add -u packages/sonya-cli/
git commit -m "refactor(sonya-cli): remove AgentManager (replaced by gateway)"
```

---

### Task 9: Integration smoke test

**Step 1: Start gateway manually**

```bash
sonya-gateway &
```

**Step 2: Test session lifecycle via curl**

```bash
# Create session
curl -s -X POST http://127.0.0.1:8340/sessions \
  -H 'Content-Type: application/json' \
  -d '{"model":"claude-sonnet-4-6","api_key":"sk-test","system_prompt":"Be brief."}'

# Chat (SSE stream)
curl -s -N -X POST http://127.0.0.1:8340/sessions/<id>/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'

# Delete session
curl -s -X DELETE http://127.0.0.1:8340/sessions/<id>
```

**Step 3: Test TUI end-to-end**

```bash
sonya chat
```
Verify: TUI launches, gateway starts automatically, chat works.

**Step 4: Kill gateway**

```bash
kill %1
```
