from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Generic, Iterator, TypeVar

from rare_identity_protocol.errors import ResourceLimitError

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class _Entry(Generic[V]):
    value: V
    expires_at: int
    revision: int


class ExpiringMap(Generic[K, V]):
    """Bounded expiring map with O(1) reads and O(log n) expiry operations."""

    def __init__(self, *, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        self._capacity = capacity
        self._entries: dict[K, _Entry[V]] = {}
        self._expiry_heap: list[tuple[int, int, K]] = []
        self._revision = 0

    def cleanup(self, *, now: int, grace_seconds: int = 30) -> None:
        cutoff = now - grace_seconds
        while self._expiry_heap and self._expiry_heap[0][0] < cutoff:
            expires_at, revision, key = heapq.heappop(self._expiry_heap)
            current = self._entries.get(key)
            if current is None:
                continue
            if current.revision != revision:
                continue
            if current.expires_at != expires_at:
                continue
            del self._entries[key]

    def set(self, *, key: K, value: V, expires_at: int, now: int, grace_seconds: int = 30) -> None:
        self.cleanup(now=now, grace_seconds=grace_seconds)
        if key not in self._entries and len(self._entries) >= self._capacity:
            raise ResourceLimitError("security replay/session store capacity exceeded")
        self._revision += 1
        revision = self._revision
        self._entries[key] = _Entry(value=value, expires_at=expires_at, revision=revision)
        heapq.heappush(self._expiry_heap, (expires_at, revision, key))

    def get(self, key: K) -> V | None:
        entry = self._entries.get(key)
        return entry.value if entry is not None else None

    def pop(self, key: K) -> V | None:
        entry = self._entries.pop(key, None)
        return entry.value if entry is not None else None

    def discard(self, key: K) -> None:
        self._entries.pop(key, None)

    def __contains__(self, key: K) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def keys(self) -> Iterator[K]:
        return iter(self._entries.keys())

    def values(self) -> Iterator[V]:
        for entry in self._entries.values():
            yield entry.value

    def items(self) -> Iterator[tuple[K, V]]:
        for key, entry in self._entries.items():
            yield key, entry.value


class ExpiringSet(Generic[K]):
    """Bounded expiring set for replay protection keys."""

    def __init__(self, *, capacity: int) -> None:
        self._store: ExpiringMap[K, bool] = ExpiringMap(capacity=capacity)

    def cleanup(self, *, now: int, grace_seconds: int = 30) -> None:
        self._store.cleanup(now=now, grace_seconds=grace_seconds)

    def add(self, *, key: K, expires_at: int, now: int, grace_seconds: int = 30) -> None:
        self._store.set(
            key=key,
            value=True,
            expires_at=expires_at,
            now=now,
            grace_seconds=grace_seconds,
        )

    def contains(self, key: K) -> bool:
        return key in self._store

    def discard(self, key: K) -> None:
        self._store.discard(key)

    def __len__(self) -> int:
        return len(self._store)
