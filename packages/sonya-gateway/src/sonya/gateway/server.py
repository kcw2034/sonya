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
