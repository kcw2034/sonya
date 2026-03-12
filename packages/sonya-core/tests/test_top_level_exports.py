"""Verify that all expected symbols are importable from sonya.core."""

from __future__ import annotations


def test_session_importable_from_sonya_core() -> None:
    from sonya.core import Session  # noqa: F401


def test_session_store_importable_from_sonya_core() -> None:
    from sonya.core import SessionStore  # noqa: F401


def test_in_memory_session_store_importable_from_sonya_core() -> None:
    from sonya.core import InMemorySessionStore  # noqa: F401


def test_logging_interceptor_already_exported() -> None:
    from sonya.core import LoggingInterceptor  # noqa: F401


def test_session_in_all() -> None:
    import sonya.core as core
    assert 'Session' in core.__all__


def test_session_store_in_all() -> None:
    import sonya.core as core
    assert 'SessionStore' in core.__all__


def test_in_memory_session_store_in_all() -> None:
    import sonya.core as core
    assert 'InMemorySessionStore' in core.__all__
