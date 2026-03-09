"""Sonya CLI entrypoint using Cyclopts."""

import getpass

from cyclopts import App

from sonya.cli.utils.auth import (
    all_providers,
    get_provider_by_name,
    check_api_key,
    save_api_key,
)

app = App(name='sonya', help='Sonya Agent Framework CLI')


@app.default
@app.command(name='chat')
def chat() -> None:
    """Launch the Sonya TUI chat interface."""
    from sonya.cli.client.app import SonyaTUI
    tui_app = SonyaTUI()
    tui_app.run()


@app.command(name='auth')
def auth(provider: str = '') -> None:
    """Set up API keys for LLM providers.

    Args:
        provider: Provider name (anthropic, openai, google).
                  If omitted, shows all providers interactively.
    """
    if provider:
        _auth_single(provider)
    else:
        _auth_interactive()


def _auth_single(provider_name: str) -> None:
    """Authenticate a single provider."""
    provider = get_provider_by_name(provider_name)
    if provider is None:
        print(
            f'Unknown provider: {provider_name}\n'
            f'Available: anthropic, openai, google'
        )
        return

    env_key = provider['env_key']
    if check_api_key(provider['prefix']):
        print(f'{provider["name"]} API key is already set.')
        overwrite = input('Overwrite? [y/N]: ').strip()
        if overwrite.lower() != 'y':
            return

    print(f'\nGet your API key at: {provider["url"]}')
    api_key = getpass.getpass(
        f'Enter {provider["name"]} API key: '
    )

    if not api_key.strip():
        print('No key entered. Skipping.')
        return

    save_api_key(env_key, api_key.strip())
    print(f'{provider["name"]} API key saved to .env')


def _auth_interactive() -> None:
    """Show all providers and authenticate interactively."""
    providers = all_providers()

    print('Sonya Auth - API Key Setup\n')

    for name, provider in providers.items():
        env_key = provider['env_key']
        has_key = check_api_key(provider['prefix'])
        status = 'configured' if has_key else 'not set'
        print(
            f'  [{name}] {provider["name"]}: {status}'
        )

    print()
    choice = input(
        'Enter provider to configure '
        '(anthropic/openai/google) or "q" to quit: '
    ).strip().lower()

    if choice == 'q' or not choice:
        return

    _auth_single(choice)


if __name__ == '__main__':
    app()
