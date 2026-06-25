"""On-demand caching fare layer.

``CachingLiveProvider`` is a cache-through FareProvider: it serves a cell from a
writable cache, and on a miss fetches it from a live provider, persists it, and
returns it re-stamped as "cached" (it is real data, now cached — the UI already
understands "cached" vs "synthetic", so no new source value leaks to the front).

The cache sits behind a small Protocol so today's in-memory store can be swapped
for a durable one (e.g. Postgres) without touching the provider — discarded
alternative: hard-coding a dict in the provider, which would couple the caching
policy to one storage backend.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Protocol

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.fares.cached import CACHED_SOURCE
from tripoptimizer.core.fares.models import Fare

logger = logging.getLogger(__name__)


class FareCacheStore(Protocol):
    def get(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None: ...

    def put(self, fare: Fare) -> None: ...


class InMemoryFareCache:
    """Process-lifetime cache keyed by (origin, destination, fly_date).

    Unbounded by design (no TTL/eviction): cardinality is airports^2 x dates,
    a few thousand entries at MVP scale, and it clears on restart. Swap in a
    bounded/durable store via the FareCacheStore Protocol if that grows.
    dict get/put are atomic under CPython's GIL, so concurrent prefetch threads
    writing distinct keys are safe.
    """

    def __init__(self) -> None:
        self._cells: dict[tuple[str, str, dt.date], Fare] = {}

    def get(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        return self._cells.get((origin, destination, fly_date))

    def put(self, fare: Fare) -> None:
        self._cells[(fare.origin, fare.destination, fare.fly_date)] = fare


class CachingLiveProvider:
    """Serve from cache; on a miss fetch live, persist, and return as cached."""

    def __init__(self, live: FareProvider, store: FareCacheStore) -> None:
        self._live = live
        self._store = store

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        cached = self._store.get(origin, destination, fly_date)
        if cached is not None:
            return cached
        fare = self._live.get_fare(origin, destination, fly_date)
        if fare is None:
            return None
        cached_fare = Fare(
            fare.origin, fare.destination, fare.fly_date, fare.price, fare.currency, CACHED_SOURCE
        )
        self._store.put(cached_fare)
        return cached_fare


class SafeLiveProvider:
    """Wrap a live provider so serving degrades instead of crashing.

    At serving, any live-source failure (rate limit, auth, transport) must fall
    through to the synthetic fallback, never 500 the user's request. Errors are
    logged (not silently swallowed) for observability — unlike the offline
    ingester, which deliberately fails loud on a systemic error like a bad token.
    """

    def __init__(self, live: FareProvider) -> None:
        self._live = live

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        try:
            return self._live.get_fare(origin, destination, fly_date)
        except Exception:  # noqa: BLE001 - serving must degrade, not crash
            logger.warning(
                "live fare fetch failed for %s->%s on %s",
                origin,
                destination,
                fly_date,
                exc_info=True,
            )
            return None
