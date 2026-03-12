"""공개 API import 테스트."""


def test_import_all_clients():
    from sonya.core import AnthropicClient, GeminiClient, OpenAIClient

    assert AnthropicClient is not None
    assert GeminiClient is not None
    assert OpenAIClient is not None


def test_import_types():
    from sonya.core import ClientConfig, Interceptor

    assert ClientConfig is not None
    assert Interceptor is not None


def test_client_config_defaults():
    from sonya.core import ClientConfig

    cfg = ClientConfig(model="test-model")
    assert cfg.model == "test-model"
    assert cfg.api_key is None
    assert cfg.interceptors == []


def test_client_config_with_api_key():
    from sonya.core import ClientConfig

    cfg = ClientConfig(model="m", api_key="sk-test")
    assert cfg.api_key == "sk-test"


def test_prompt_exports():
    from sonya.core import Prompt, Example
    assert Prompt is not None
    assert Example is not None


def test_get_adapter_is_public():
    # get_adapter (no underscore) must be importable from sonya.core
    from sonya.core import get_adapter
    assert get_adapter is not None


def test_get_adapter_returns_correct_adapter():
    from sonya.core import get_adapter, ClientConfig
    from sonya.core.client.base import BaseClient
    from sonya.core.parsers.adapter import (
        AnthropicAdapter,
    )
    from typing import Any, AsyncIterator

    class FakeAnthropicClient(BaseClient):
        def __init__(self) -> None:
            super().__init__(ClientConfig(model='claude-test'))

        async def _provider_generate(
            self, messages: list[dict[str, Any]], **kwargs: Any
        ) -> Any:
            return None

        async def _provider_generate_stream(
            self, messages: list[dict[str, Any]], **kwargs: Any
        ) -> AsyncIterator[Any]:
            yield None

    # Patch the class name to match the registry key
    FakeAnthropicClient.__name__ = 'AnthropicClient'
    adapter = get_adapter(FakeAnthropicClient())
    assert isinstance(adapter, AnthropicAdapter)
