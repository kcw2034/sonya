"""Authentication utilities for Sonya CLI."""

import os
from pathlib import Path

_PROVIDERS: dict[str, dict[str, str]] = {
    'anthropic': {
        'env_key': 'ANTHROPIC_API_KEY',
        'name': 'Anthropic',
        'url': 'https://console.anthropic.com/settings/keys',
        'prefix': 'claude',
    },
    'openai': {
        'env_key': 'OPENAI_API_KEY',
        'name': 'OpenAI',
        'url': 'https://platform.openai.com/api-keys',
        'prefix': 'gpt',
    },
    'google': {
        'env_key': 'GOOGLE_API_KEY',
        'name': 'Google',
        'url': 'https://aistudio.google.com/apikey',
        'prefix': 'gemini',
    },
}


def _find_dotenv() -> Path:
    """Find or create the .env file path."""
    cwd = Path.cwd()
    env_path = cwd / '.env'
    return env_path


def get_provider_by_model(model: str) -> dict[str, str] | None:
    """Return provider info dict for a given model string.

    Args:
        model: The model identifier string.

    Returns:
        Provider info dict or None if unknown.
    """
    for provider in _PROVIDERS.values():
        if model.startswith(provider['prefix']):
            return provider
    return None


def get_provider_by_name(name: str) -> dict[str, str] | None:
    """Return provider info dict by provider name.

    Args:
        name: Provider name (anthropic, openai, google).

    Returns:
        Provider info dict or None if unknown.
    """
    return _PROVIDERS.get(name)


def all_providers() -> dict[str, dict[str, str]]:
    """Return all provider configurations.

    Returns:
        Dict of all provider info dicts.
    """
    return _PROVIDERS.copy()


def check_api_key(model: str) -> bool:
    """Check if the API key for the model's provider exists.

    Args:
        model: The model identifier string.

    Returns:
        True if the API key is set, False otherwise.
    """
    provider = get_provider_by_model(model)
    if provider is None:
        return False
    return bool(os.environ.get(provider['env_key']))


def save_api_key(env_key: str, api_key: str) -> None:
    """Save an API key to the .env file and set it
    in the current environment.

    Args:
        env_key: The environment variable name.
        api_key: The API key value.
    """
    os.environ[env_key] = api_key

    env_path = _find_dotenv()
    lines: list[str] = []

    if env_path.exists():
        lines = env_path.read_text().splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f'{env_key}='):
            lines[i] = f'{env_key}={api_key}'
            updated = True
            break

    if not updated:
        lines.append(f'{env_key}={api_key}')

    env_path.write_text('\n'.join(lines) + '\n')
