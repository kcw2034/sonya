"""Request and response schemas for the gateway API."""

from pydantic import BaseModel, field_validator

# Known model name prefixes — extend here when adding new providers.
_VALID_MODEL_PREFIXES: tuple[str, ...] = ('claude', 'gpt', 'gemini')


class CreateSessionRequest(BaseModel):
    """Request body for POST /sessions."""

    model: str
    api_key: str = ''
    system_prompt: str = ''

    @field_validator('model')
    @classmethod
    def _validate_model_prefix(cls, v: str) -> str:
        """Reject model names with unknown provider prefixes."""
        if not v:
            raise ValueError('model must not be empty')
        if not any(
            v.startswith(p) for p in _VALID_MODEL_PREFIXES
        ):
            raise ValueError(
                f'Unsupported model prefix. '
                f'Must start with one of: '
                f'{_VALID_MODEL_PREFIXES}'
            )
        return v


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
