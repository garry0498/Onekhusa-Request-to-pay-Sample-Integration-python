"""A tiny TTL-backed status cache.

Mirrors Laravel's Cache::put("status_{$reference}", $value, 1800) — keeps the
demo dependency-free while matching the "cache-backed status polling" design.
A dictionary with expiry timestamps is enough for a single-process demo.
"""

import time


class StatusCache:
    """Simple in-memory cache with per-key TTL."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._expires: dict[str, float] = {}

    def put(self, key: str, value: str, ttl: int = 1800) -> None:
        self._store[key] = value
        self._expires[key] = time.time() + ttl

    def get(self, key: str, default: str | None = None) -> str | None:
        expires_at = self._expires.get(key)
        if expires_at is None or time.time() > expires_at:
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return default
        return self._store.get(key, default)


# Shared instance used by routes and webhooks.
status_cache = StatusCache()
