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
