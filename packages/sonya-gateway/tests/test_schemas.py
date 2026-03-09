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
