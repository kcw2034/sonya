"""Sonya Gateway — REST + SSE server for LLM sessions."""

import uvicorn


def run_server(
    host: str = '127.0.0.1',
    port: int = 8340,
) -> None:
    """Start the gateway server.

    Args:
        host: Bind address.
        port: Bind port.
    """
    uvicorn.run(
        'sonya.gateway.server:app',
        host=host,
        port=port,
    )
