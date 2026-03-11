"""Tests for gateway SessionManager."""

import pytest

from unittest.mock import MagicMock, patch

from sonya.gateway.session import SessionManager


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager()


class TestSessionLifecycle:

    def test_create_session(self, manager: SessionManager) -> None:
        with patch(
            'sonya.gateway.session._create_provider_client'
        ) as mock_client, patch(
            'sonya.gateway.session.get_adapter'
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
            'sonya.gateway.session.get_adapter'
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
            'sonya.gateway.session.get_adapter'
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
            'sonya.gateway.session.get_adapter'
        ):
            sid = manager.create(
                model='claude-sonnet-4-6',
                api_key='sk-test',
                system_prompt='old',
            )
            manager.update(sid, system_prompt='new')
            session = manager.get(sid)
            assert session['system_prompt'] == 'new'
