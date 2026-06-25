"""On-demand caching fare layer: serve from cache, else fetch live + persist."""

import datetime as dt

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.on_demand import (
    CachingLiveProvider,
    InMemoryFareCache,
    SafeLiveProvider,
)

DATE = dt.date(2026, 7, 1)


def _fare(source: str = "travelpayouts", price: float = 50.0) -> Fare:
    return Fare("LIS", "BCN", DATE, price, "EUR", source)


class _RecordingProvider:
    """A live provider that counts calls and returns a preset fare (or None)."""

    def __init__(self, fare: Fare | None) -> None:
        self._fare = fare
        self.calls = 0

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        self.calls += 1
        return self._fare


def test_in_memory_cache_miss_returns_none() -> None:
    assert InMemoryFareCache().get("LIS", "BCN", DATE) is None


def test_in_memory_cache_put_then_get() -> None:
    cache = InMemoryFareCache()
    cache.put(_fare(price=42.0))
    got = cache.get("LIS", "BCN", DATE)
    assert got is not None and got.price == 42.0


def test_caching_live_serves_from_cache_without_calling_live() -> None:
    cache = InMemoryFareCache()
    cache.put(_fare(source="cached", price=30.0))
    live = _RecordingProvider(_fare(price=99.0))
    provider = CachingLiveProvider(live, cache)

    got = provider.get_fare("LIS", "BCN", DATE)

    assert got is not None and got.price == 30.0  # served from cache
    assert live.calls == 0  # live never touched on a hit


def test_caching_live_fetches_persists_and_restamps_on_miss() -> None:
    cache = InMemoryFareCache()
    live = _RecordingProvider(_fare(source="travelpayouts", price=55.0))
    provider = CachingLiveProvider(live, cache)

    got = provider.get_fare("LIS", "BCN", DATE)

    assert got is not None and got.price == 55.0
    assert got.source == "cached"  # re-stamped so the UI needs no new source value
    assert live.calls == 1
    assert cache.get("LIS", "BCN", DATE) is not None  # persisted for next time


def test_caching_live_second_call_hits_cache() -> None:
    live = _RecordingProvider(_fare(price=55.0))
    provider = CachingLiveProvider(live, InMemoryFareCache())

    provider.get_fare("LIS", "BCN", DATE)
    provider.get_fare("LIS", "BCN", DATE)

    assert live.calls == 1  # second call served from the now-warm cache


def test_caching_live_returns_none_and_stores_nothing_when_live_has_no_data() -> None:
    cache = InMemoryFareCache()
    live = _RecordingProvider(None)
    provider = CachingLiveProvider(live, cache)

    assert provider.get_fare("LIS", "BCN", DATE) is None
    assert cache.get("LIS", "BCN", DATE) is None  # a miss is not cached


class _RaisingLive:
    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        raise RuntimeError("upstream blew up")


def test_safe_live_passes_fare_through() -> None:
    got = SafeLiveProvider(_RecordingProvider(_fare(price=12.0))).get_fare("LIS", "BCN", DATE)
    assert got is not None and got.price == 12.0


def test_safe_live_swallows_exceptions_to_none() -> None:
    # Serving must degrade to synthetic, never crash, on a live-source error.
    assert SafeLiveProvider(_RaisingLive()).get_fare("LIS", "BCN", DATE) is None
