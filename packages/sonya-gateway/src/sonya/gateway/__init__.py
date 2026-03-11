"""Sonya Gateway — REST + SSE server for LLM sessions."""

import os

import uvicorn


def run_server(
    host: str = '0.0.0.0',
    port: int | None = None,
) -> None:
    """Start the gateway server.

    Args:
        host: Bind address.
        port: Bind port. Defaults to PORT env var or 8340.
    """
    if port is None:
        port = int(os.environ.get('PORT', '8340'))
    uvicorn.run(
        'sonya.gateway.server:app',
        host=host,
        port=port,
    )
