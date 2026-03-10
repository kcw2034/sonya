"""FastAPI server for the Sonya Gateway."""

import json
import os
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from sonya.gateway.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    UpdateSessionRequest,
    ChatRequest,
)
from sonya.gateway.session import SessionManager

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
    {'id': 'claude-sonnet-4-6', 'name': 'Claude 4.6 Sonnet'},
    {'id': 'claude-haiku-4-5-20251001', 'name': 'Claude 4.5 Haiku'},
    {'id': 'gpt-4o', 'name': 'GPT-4o'},
    {'id': 'gpt-4.1', 'name': 'GPT-4.1'},
    {'id': 'gpt-4.1-mini', 'name': 'GPT-4.1 mini'},
    {'id': 'gemini-3-flash-preview', 'name': 'Gemini 3 Flash'},
    {'id': 'gemini-3.1-pro-preview', 'name': 'Gemini 3.1 Pro'},
]


@app.get('/')
async def index(request: Request):
    """Serve the chat GUI."""
    return _templates.TemplateResponse(
        'chat.html',
        {'request': request, 'models': _MODELS},
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
