"""In-memory TTL cache utilities."""

from __future__ import annotations

import threading
import time
from typing import Any

from anime_weather.config import settings


class TTLCache:
    """A simple thread-safe in-memory cache with time-based expiration."""

    def __init__(self, default_ttl: int = 1800) -> None:
        self.default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Return a cached value if it exists and has not expired."""
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            expiry, value = entry
            if expiry <= now:
                self._store.pop(key, None)
                return None

            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value using the provided TTL or the default TTL."""
        effective_ttl = self.default_ttl if ttl is None else ttl
        expiry = time.monotonic() + max(effective_ttl, 1)
        with self._lock:
            self._store[key] = (expiry, value)

    def clear_expired(self) -> int:
        """Remove expired entries and return the number removed."""
        now = time.monotonic()
        with self._lock:
            expired_keys = [key for key, (expiry, _) in self._store.items() if expiry <= now]
            for key in expired_keys:
                self._store.pop(key, None)
            return len(expired_keys)


weather_cache = TTLCache(default_ttl=settings.cache_ttl or settings.weather_cache_ttl_seconds)
anime_cache = TTLCache(default_ttl=settings.anime_trending_cache_ttl_seconds)
quote_cache = TTLCache(default_ttl=settings.quote_cache_ttl_seconds)
geocode_cache = TTLCache(default_ttl=settings.geocode_cache_ttl_seconds)
