"""Tests for gateway FastAPI server."""

import pytest

from unittest.mock import patch, MagicMock

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
async def test_chat_session_not_found(
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


@pytest.mark.asyncio
async def test_chat_stream_error_yields_sse_error_event(
    mock_session_manager,
) -> None:
    """When chat_stream raises a known error, an SSE error event is yielded."""
    import json as _json

    mock_session_manager.get.return_value = {'model': 'test'}

    async def _raise_key_error(session_id, message):
        raise KeyError('session gone')
        yield  # make it an async generator

    mock_session_manager.chat_stream = _raise_key_error

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url='http://test',
    ) as client:
        resp = await client.post(
            '/sessions/abc/chat',
            json={'message': 'hello'},
        )

    # SSE streams always return 200; errors are in the event payload
    assert resp.status_code == 200
    # Find the 'error' event in the response body
    body = resp.text
    assert 'error' in body
