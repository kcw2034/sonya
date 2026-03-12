"""BaseClient and interceptor chain tests."""

import pytest

from sonya.core.schemas.types import ClientConfig
from sonya.core.client.base import BaseClient
from typing import Any, AsyncIterator


class DummyClient(BaseClient):
    """Dummy client for testing."""

    async def _provider_generate(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        return {"echo": messages, **kwargs}

    async def _provider_generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Any]:
        for msg in messages:
            yield msg


class LogInterceptor:
    """Test interceptor that records before/after calls."""

    def __init__(self) -> None:
        self.before_calls: list[tuple] = []
        self.after_calls: list[Any] = []

    async def before_request(self, messages, kwargs):
        self.before_calls.append((messages, kwargs))
        return messages, kwargs

    async def after_response(self, response):
        self.after_calls.append(response)
        return response


@pytest.mark.asyncio
async def test_generate_returns_response():
    client = DummyClient(ClientConfig(model="test"))
    result = await client.generate([{"role": "user", "content": "hi"}])
    assert result["echo"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_generate_stream_yields_messages():
    client = DummyClient(ClientConfig(model="test"))
    msgs = [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
    chunks = [c async for c in client.generate_stream(msgs)]
    assert chunks == msgs


@pytest.mark.asyncio
async def test_interceptor_chain():
    interceptor = LogInterceptor()
    client = DummyClient(ClientConfig(model="test", interceptors=[interceptor]))
    await client.generate([{"role": "user", "content": "hello"}])

    assert len(interceptor.before_calls) == 1
    assert len(interceptor.after_calls) == 1


@pytest.mark.asyncio
async def test_async_context_manager():
    async with DummyClient(ClientConfig(model="test")) as client:
        result = await client.generate([{"role": "user", "content": "hi"}])
        assert "echo" in result


def test_abstract_method_enforced_on_subclass() -> None:
    """BaseClient subclass that omits _provider_generate must raise
    TypeError at instantiation — not silently succeed and fail later."""
    import pytest

    class IncompleteClient(BaseClient):
        """Subclass that intentionally omits _provider_generate."""
        pass

    with pytest.raises(TypeError):
        IncompleteClient(ClientConfig(model='test'))
