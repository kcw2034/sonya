"""Sonya Gateway — REST + SSE server for LLM sessions."""

import os

import uvicorn


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
    uvicorn.run(
        'sonya.gateway.server:app',
        host=host,
        port=port,
    )
