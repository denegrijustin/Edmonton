"""Cache management utilities."""

import time
from typing import Any, Dict, Optional


class SourceCache:
    """Simple in-memory cache with timestamp tracking."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._timestamps[key] = time.time()

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def get_timestamp(self, key: str) -> Optional[float]:
        return self._timestamps.get(key)

    def is_fresh(self, key: str, ttl: float) -> bool:
        ts = self._timestamps.get(key)
        if ts is None:
            return False
        return (time.time() - ts) < ttl

    def clear(self, key: str) -> None:
        self._store.pop(key, None)
        self._timestamps.pop(key, None)
