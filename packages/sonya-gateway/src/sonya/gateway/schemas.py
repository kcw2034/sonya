"""Request and response schemas for the gateway API."""

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    """Request body for POST /sessions."""

    model: str
    api_key: str = ''
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
