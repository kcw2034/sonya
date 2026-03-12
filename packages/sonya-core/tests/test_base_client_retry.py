"""Tests for BaseClient retry / exponential-backoff behaviour."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from sonya.core.client.provider.base import BaseClient
from sonya.core.exceptions.errors import MaxRetriesExceededError
from sonya.core.schemas.types import ClientConfig, RetryConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Client(BaseClient):
    """Minimal concrete client for testing."""

    def __init__(
        self,
        config: ClientConfig,
        side_effects: list[Any],
    ) -> None:
        super().__init__(config)
        self._side_effects = list(side_effects)
        self._call_count = 0

    async def _provider_generate(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        effect = self._side_effects[self._call_count]
        self._call_count += 1
        if isinstance(effect, Exception):
            raise effect
        return effect

    async def _provider_generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield 'chunk'


def _config(retry: RetryConfig) -> ClientConfig:
    return ClientConfig(model='test', retry=retry)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_error_returns_immediately() -> None:
    """Successful call on first attempt — no sleep, returns response."""
    cfg = _config(RetryConfig(max_retries=3))
    client = _Client(cfg, ['ok'])

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        result = await client.generate([])

    assert result == 'ok'
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt() -> None:
    """First attempt raises retryable error; second attempt succeeds."""
    cfg = _config(RetryConfig(max_retries=3, base_delay=0.0))
    client = _Client(cfg, [OSError('timeout'), 'ok'])

    with patch('asyncio.sleep', new_callable=AsyncMock):
        result = await client.generate([])

    assert result == 'ok'
    assert client._call_count == 2


@pytest.mark.asyncio
async def test_all_retries_exhausted_raises() -> None:
    """All attempts fail → MaxRetriesExceededError is raised."""
    cfg = _config(RetryConfig(max_retries=2, base_delay=0.0))
    errors = [OSError('fail')] * 3  # initial + 2 retries
    client = _Client(cfg, errors)

    with patch('asyncio.sleep', new_callable=AsyncMock):
        with pytest.raises(MaxRetriesExceededError) as exc_info:
            await client.generate([])

    assert client._call_count == 3  # 1 initial + 2 retries
    assert exc_info.value.attempts == 3


@pytest.mark.asyncio
async def test_max_retries_zero_no_retry() -> None:
    """max_retries=0 means no retry; exception propagates on first failure."""
    cfg = _config(RetryConfig(max_retries=0))
    client = _Client(cfg, [OSError('fail')])

    with pytest.raises(MaxRetriesExceededError):
        await client.generate([])

    assert client._call_count == 1


@pytest.mark.asyncio
async def test_non_retryable_exception_propagates_immediately() -> None:
    """ValueError is not in retryable_exceptions — propagates without retry."""
    cfg = _config(
        RetryConfig(
            max_retries=3,
            retryable_exceptions=(OSError,),
        )
    )
    client = _Client(cfg, [ValueError('bad input'), 'ok'])

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(ValueError):
            await client.generate([])

    mock_sleep.assert_not_called()
    assert client._call_count == 1


@pytest.mark.asyncio
async def test_backoff_delay_grows_exponentially() -> None:
    """Sleep durations follow base_delay * backoff_factor^attempt."""
    cfg = _config(
        RetryConfig(
            max_retries=3,
            base_delay=1.0,
            backoff_factor=2.0,
            max_delay=100.0,
        )
    )
    client = _Client(cfg, [OSError()] * 4)

    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    with patch('asyncio.sleep', side_effect=_fake_sleep):
        with pytest.raises(MaxRetriesExceededError):
            await client.generate([])

    # Delays: 1.0, 2.0, 4.0
    assert sleep_calls == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_backoff_capped_at_max_delay() -> None:
    """Sleep duration never exceeds max_delay."""
    cfg = _config(
        RetryConfig(
            max_retries=5,
            base_delay=10.0,
            backoff_factor=10.0,
            max_delay=30.0,
        )
    )
    client = _Client(cfg, [OSError()] * 6)

    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    with patch('asyncio.sleep', side_effect=_fake_sleep):
        with pytest.raises(MaxRetriesExceededError):
            await client.generate([])

    assert all(d <= 30.0 for d in sleep_calls)


@pytest.mark.asyncio
async def test_last_error_chained_in_exception() -> None:
    """MaxRetriesExceededError chains the original exception."""
    original = OSError('network error')
    cfg = _config(RetryConfig(max_retries=1, base_delay=0.0))
    client = _Client(cfg, [original, original])

    with patch('asyncio.sleep', new_callable=AsyncMock):
        with pytest.raises(MaxRetriesExceededError) as exc_info:
            await client.generate([])

    assert exc_info.value.__cause__ is original


@pytest.mark.asyncio
async def test_retry_config_defaults() -> None:
    """Default RetryConfig has max_retries=3 and retries on OSError."""
    rc = RetryConfig()
    assert rc.max_retries == 3
    assert rc.base_delay == 1.0
    assert rc.max_delay == 60.0
    assert rc.backoff_factor == 2.0
    assert OSError in rc.retryable_exceptions


@pytest.mark.asyncio
async def test_client_config_defaults_to_retry() -> None:
    """ClientConfig without explicit retry uses RetryConfig defaults."""
    cfg = ClientConfig(model='test')
    assert isinstance(cfg.retry, RetryConfig)
    assert cfg.retry.max_retries == 3


@pytest.mark.asyncio
async def test_generate_stream_not_retried() -> None:
    """generate_stream() does NOT retry on failure."""
    cfg = _config(RetryConfig(max_retries=3, base_delay=0.0))

    class _FailStreamClient(BaseClient):
        def __init__(self, config: ClientConfig) -> None:
            super().__init__(config)
            self.stream_call_count = 0

        async def _provider_generate(
            self,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> Any:
            return 'ok'

        async def _provider_generate_stream(
            self,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> AsyncIterator[Any]:
            self.stream_call_count += 1
            raise OSError('stream failed')
            yield  # make it an async generator

    client = _FailStreamClient(cfg)

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(OSError):
            async for _ in client.generate_stream([]):
                pass

    mock_sleep.assert_not_called()
    assert client.stream_call_count == 1
