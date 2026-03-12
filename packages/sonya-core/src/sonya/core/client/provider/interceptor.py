"""LoggingInterceptor — logs LLM requests and responses."""

from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from typing import Any

from sonya.core.schemas.events import (
    LLMRequestEvent,
    LLMResponseEvent,
)

_logger = logging.getLogger('sonya.client')


def extract_usage(response: Any) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from any provider response.

    Supports Anthropic, OpenAI, Gemini, and dict-format responses.
    Returns (0, 0) when no usage information is found.

    Args:
        response: Native provider response object or dict.

    Returns:
        Tuple of (input_tokens, output_tokens).
    """
    # Object with usage attribute (Anthropic / OpenAI)
    usage = getattr(response, 'usage', None)
    if usage is not None:
        inp = getattr(
            usage, 'input_tokens',
            getattr(usage, 'prompt_tokens', 0),
        )
        out = getattr(
            usage, 'output_tokens',
            getattr(usage, 'completion_tokens', 0),
        )
        return int(inp), int(out)
    # Gemini usage_metadata
    meta = getattr(response, 'usage_metadata', None)
    if meta is not None:
        return (
            int(getattr(meta, 'prompt_token_count', 0)),
            int(getattr(meta, 'candidates_token_count', 0)),
        )
    # Dict fallback
    if isinstance(response, dict):
        u = response.get('usage', {})
        return (
            int(u.get('input_tokens', u.get('prompt_tokens', 0))),
            int(u.get('output_tokens', u.get('completion_tokens', 0))),
        )
    return 0, 0


class LoggingInterceptor:
    """Interceptor that logs LLM request/response details.

    Per-request state (start time, model name) is stored in
    :class:`contextvars.ContextVar` instances so that concurrent
    asyncio tasks sharing the same interceptor each maintain
    independent state.

    Args:
        level: Logging level (default: DEBUG).
        log_json: If True, emit structured JSON log lines.
    """

    def __init__(
        self,
        level: int = logging.DEBUG,
        log_json: bool = False,
    ) -> None:
        self._level = level
        self._log_json = log_json
        # Use unique names (keyed on object id) so multiple
        # interceptor instances each have their own ContextVars.
        _uid = id(self)
        self._request_start: ContextVar[float] = ContextVar(
            f'sonya_log_start_{_uid}', default=0.0
        )
        self._model: ContextVar[str] = ContextVar(
            f'sonya_log_model_{_uid}', default=''
        )

    async def before_request(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Record request start time and emit LLMRequestEvent."""
        self._request_start.set(time.monotonic())
        model = kwargs.get('model', '')
        self._model.set(model)

        event = LLMRequestEvent(
            model=model,
            message_count=len(messages),
            kwargs_keys=tuple(kwargs.keys()),
        )
        self._emit(event)
        return messages, kwargs

    async def after_response(
        self, response: Any
    ) -> Any:
        """Calculate latency, extract usage, and emit LLMResponseEvent."""
        request_start = self._request_start.get()
        model = self._model.get()
        latency_ms = (
            (time.monotonic() - request_start) * 1000
            if request_start
            else 0.0
        )

        stop_reason = self._extract_stop_reason(
            response
        )
        input_tokens, output_tokens = (
            self._extract_usage(response)
        )

        event = LLMResponseEvent(
            model=model,
            stop_reason=stop_reason,
            latency_ms=round(latency_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self._emit(event)
        return response

    def _extract_stop_reason(
        self, response: Any
    ) -> str | None:
        """Extract stop reason from provider-agnostic response."""
        # Anthropic
        if hasattr(response, 'stop_reason'):
            return str(response.stop_reason)
        # OpenAI
        if (
            hasattr(response, 'choices')
            and response.choices
        ):
            return getattr(
                response.choices[0],
                'finish_reason',
                None,
            )
        # Gemini
        if (
            hasattr(response, 'candidates')
            and response.candidates
        ):
            candidate = response.candidates[0]
            reason = getattr(
                candidate, 'finish_reason', None
            )
            return (
                str(reason) if reason is not None
                else None
            )
        # Dict fallback
        if isinstance(response, dict):
            return response.get(
                'stop_reason',
                response.get('finish_reason'),
            )
        return None

    def _extract_usage(
        self, response: Any
    ) -> tuple[int, int]:
        """Extract token usage from provider-agnostic response."""
        return extract_usage(response)

    def _emit(
        self,
        event: LLMRequestEvent | LLMResponseEvent,
    ) -> None:
        """Log the event in human-readable or JSON format."""
        if self._log_json:
            data = {
                'event': event.event_type,
                'timestamp': event.timestamp,
            }
            if isinstance(event, LLMRequestEvent):
                data.update({
                    'model': event.model,
                    'message_count': (
                        event.message_count
                    ),
                    'kwargs_keys': list(
                        event.kwargs_keys
                    ),
                })
            elif isinstance(event, LLMResponseEvent):
                data.update({
                    'model': event.model,
                    'stop_reason': event.stop_reason,
                    'latency_ms': event.latency_ms,
                    'input_tokens': event.input_tokens,
                    'output_tokens': (
                        event.output_tokens
                    ),
                })
            _logger.log(
                self._level, json.dumps(data)
            )
        else:
            if isinstance(event, LLMRequestEvent):
                _logger.log(
                    self._level,
                    '[LLM Request] model=%s messages=%d',
                    event.model,
                    event.message_count,
                )
            elif isinstance(event, LLMResponseEvent):
                _logger.log(
                    self._level,
                    '[LLM Response] model=%s stop=%s '
                    'latency=%.1fms tokens=%d/%d',
                    event.model,
                    event.stop_reason,
                    event.latency_ms,
                    event.input_tokens,
                    event.output_tokens,
                )
