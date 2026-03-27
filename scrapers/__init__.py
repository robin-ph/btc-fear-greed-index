"""Shared utilities for Playwright scrapers."""

_PROXY_ERRORS = ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED")


class ProxyBroken(Exception):
    """Raised when system proxy is unreachable — signals retry without proxy."""
    pass


def is_proxy_error(exc: Exception) -> bool:
    return any(e in str(exc) for e in _PROXY_ERRORS)
