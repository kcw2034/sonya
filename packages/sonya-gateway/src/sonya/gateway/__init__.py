"""Sonya Gateway — REST + SSE server for LLM sessions."""

import os

import uvicorn

_BANNER = r"""
  _____
 / ____|
| (___   ___  _ __  _   _  __ _
 \___ \ / _ \| '_ \| | | |/ _` |
 ____) | (_) | | | | |_| | (_| |
|_____/ \___/|_| |_|\__, |\__,_|
                     __/ |
                    |___/   Gateway
"""


def _print_banner(host: str, port: int) -> None:
    """Print the startup banner with server address.

    Args:
        host: Bound host address.
        port: Bound port number.
    """
    print(_BANNER)
    print(f'  Listening on  http://{host}:{port}')
    print('  Press Ctrl+C to stop.\n')


def run_server(
    host: str = '127.0.0.1',
    port: int | None = None,
) -> None:
    """Start the gateway server.

    Args:
        host: Bind address. Defaults to 127.0.0.1 (localhost only).
            Set to '0.0.0.0' explicitly for remote access.
        port: Bind port. Defaults to PORT env var or 8340.
    """
    if port is None:
        port = int(os.environ.get('PORT', '8340'))
    _print_banner(host, port)
    uvicorn.run(
        'sonya.gateway.server:app',
        host=host,
        port=port,
        log_level='warning',
    )
