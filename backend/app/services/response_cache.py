from collections.abc import Callable, Hashable
from threading import Lock
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


class TtlCache:
    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        self._items: dict[Hashable, tuple[float, float, object]] = {}
        self._lock = Lock()

    def get_or_set(self, key: Hashable, ttl_seconds: int, factory: Callable[[], T]) -> T:
        now = monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                expires_at, _created_at, value = item
                if expires_at > now:
                    return value  # type: ignore[return-value]
                self._items.pop(key, None)

        value = factory()
        with self._lock:
            self._prune(now)
            self._items[key] = (now + ttl_seconds, now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def _prune(self, now: float) -> None:
        expired_keys = [
            key
            for key, (expires_at, _created_at, _value) in self._items.items()
            if expires_at <= now
        ]
        for key in expired_keys:
            self._items.pop(key, None)

        while len(self._items) >= self.max_entries:
            oldest_key = min(self._items, key=lambda key: self._items[key][1])
            self._items.pop(oldest_key, None)


public_response_cache = TtlCache(max_entries=80)


def clear_public_response_cache() -> None:
    public_response_cache.clear()
