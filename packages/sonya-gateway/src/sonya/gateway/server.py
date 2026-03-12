"""FastAPI server for the Sonya Gateway."""

import json
import os
import time
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from .schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    UpdateSessionRequest,
    ChatRequest,
)
from .session import SessionManager

app = FastAPI(title='Sonya Gateway')
session_manager = SessionManager()

_base_dir = os.path.dirname(os.path.abspath(__file__))

app.mount(
    '/static',
    StaticFiles(
        directory=os.path.join(_base_dir, 'static')
    ),
    name='static',
)

_templates = Jinja2Templates(
    directory=os.path.join(_base_dir, 'templates')
)

_MODELS = [
    {
        'id': 'claude-sonnet-4-6',
        'name': 'Claude 4.6 Sonnet',
        'short': 'Sonnet',
    },
    {
        'id': 'claude-haiku-4-5-20251001',
        'name': 'Claude 4.5 Haiku',
        'short': 'Haiku',
    },
    {
        'id': 'gpt-4o',
        'name': 'GPT-4o',
        'short': 'GPT-4o',
    },
    {
        'id': 'gpt-4.1',
        'name': 'GPT-4.1',
        'short': 'GPT-4.1',
    },
    {
        'id': 'gpt-4.1-mini',
        'name': 'GPT-4.1 mini',
        'short': '4.1 mini',
    },
    {
        'id': 'gemini-3-flash-preview',
        'name': 'Gemini 3 Flash',
        'short': 'Flash',
    },
    {
        'id': 'gemini-3.1-pro-preview',
        'name': 'Gemini 3.1 Pro',
        'short': 'Pro',
    },
]

_MODEL_KEY_MAP = {
    'claude': 'ANTHROPIC_API_KEY',
    'gpt': 'OPENAI_API_KEY',
    'gemini': 'GOOGLE_API_KEY',
}


def _resolve_api_key(
    model: str, provided_key: str
) -> str:
    """Resolve API key from provided value or env.

    Args:
        model: Model identifier string.
        provided_key: User-provided API key.

    Returns:
        Resolved API key string (may be empty if not found).
    """
    if provided_key:
        return provided_key
    for prefix, env_var in _MODEL_KEY_MAP.items():
        if model.startswith(prefix):
            return os.environ.get(env_var, '')
    return ''


def _safe_error_message(e: Exception) -> str:
    """Produce a client-safe error message.

    Returns only the exception class name. The raw message is
    intentionally omitted to prevent leaking internal file paths,
    stack traces, or API key fragments to clients. Full details
    are available in server logs.

    Args:
        e: The exception to sanitise.

    Returns:
        A short, safe error string containing only the type name.
    """
    return type(e).__name__


@app.get('/')
async def index(request: Request):
    """Serve the chat GUI."""
    return _templates.TemplateResponse(
        'chat.html',
        {
            'request': request,
            'models': _MODELS,
            'version': int(time.time()),
        },
    )


@app.post(
    '/sessions',
    response_model=CreateSessionResponse,
    status_code=201,
)
async def create_session(
    body: CreateSessionRequest,
) -> CreateSessionResponse:
    """Create a new LLM session."""
    api_key = _resolve_api_key(
        body.model, body.api_key
    )
    if not api_key:
        return JSONResponse(
            status_code=400,
            content={
                'detail': (
                    'API key required. Provide api_key in '
                    'the request body or set the appropriate '
                    'environment variable '
                    '(ANTHROPIC_API_KEY, OPENAI_API_KEY, '
                    'GOOGLE_API_KEY).'
                ),
            },
        )
    session_id = session_manager.create(
        model=body.model,
        api_key=api_key,
        system_prompt=body.system_prompt,
    )
    return CreateSessionResponse(
        session_id=session_id,
        model=body.model,
    )


@app.get('/sessions')
async def list_sessions() -> list[dict]:
    """List all active sessions."""
    return session_manager.list_all()


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
        except (KeyError, ValueError, RuntimeError, OSError) as e:
            # KeyError: session not found
            # ValueError/RuntimeError: LLM config or API errors
            # OSError: network-level failures (ConnectionError,
            #          TimeoutError, etc. are all OSError subclasses)
            yield {
                'event': 'error',
                'data': json.dumps(
                    {'message': _safe_error_message(e)}
                ),
            }

    return EventSourceResponse(_stream())
