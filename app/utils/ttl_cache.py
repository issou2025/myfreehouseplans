from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Callable, Dict, Generic, Optional, Tuple, TypeVar


K = TypeVar('K')
V = TypeVar('V')


@dataclass
class _Entry(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """Small in-process TTL cache.

    - Best-effort only (safe to lose on restart)
    - Thread-safe
    - Designed for expensive computations (recommendations/facets/intelligence)
    """

    def __init__(self, ttl_seconds: int = 60, max_items: int = 2048):
        self._ttl = max(1, int(ttl_seconds))
        self._max = max(64, int(max_items))
        self._data: Dict[K, _Entry[V]] = {}
        self._lock = RLock()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def get(self, key: K) -> Optional[V]:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            if entry.expires_at <= now:
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: K, value: V, ttl_seconds: Optional[int] = None) -> None:
        ttl = self._ttl if ttl_seconds is None else max(1, int(ttl_seconds))
        expires_at = time.time() + ttl
        with self._lock:
            if len(self._data) >= self._max:
                # naive eviction: drop expired, then drop oldest-ish (first key)
                self._prune_locked()
                if len(self._data) >= self._max:
                    try:
                        first = next(iter(self._data))
                        self._data.pop(first, None)
                    except StopIteration:
                        pass
            self._data[key] = _Entry(value=value, expires_at=expires_at)

    def get_or_set(self, key: K, factory: Callable[[], V], ttl_seconds: Optional[int] = None) -> V:
        existing = self.get(key)
        if existing is not None:
            return existing
        value = factory()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._data.items() if v.expires_at <= now]
        for k in expired:
            self._data.pop(k, None)
