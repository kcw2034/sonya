"""Tests for GatewayClient."""

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from sonya.cli.client.gateway_client import GatewayClient


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> MagicMock:
    """Create a mock httpx Response (sync methods)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


class TestGatewayClient:

    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        client = GatewayClient(base_url='http://test')

        mock_resp = _make_response(
            status_code=201,
            json_data={
                'session_id': 'abc123',
                'model': 'claude-sonnet-4-6',
            },
        )

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

        mock_resp = _make_response(status_code=204)

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

        mock_resp = _make_response(status_code=200)

        with patch.object(
            client._http, 'patch',
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            await client.update_session(
                system_prompt='New prompt'
            )

    @pytest.mark.asyncio
    async def test_no_session_raises(self) -> None:
        client = GatewayClient(base_url='http://test')
        with pytest.raises(RuntimeError):
            await client.update_session(
                system_prompt='test'
            )
