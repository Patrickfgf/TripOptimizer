"""On-demand caching fare layer: serve from cache, else fetch live + persist."""

import datetime as dt

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.on_demand import (
    CachingLiveProvider,
    CachingMonthProvider,
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


# --- CachingMonthProvider: one month fetch warms ~30 cells --------------------

_AUG10 = dt.date(2026, 8, 10)
_AUG11 = dt.date(2026, 8, 11)  # a day with no price in the month payload
_AUG12 = dt.date(2026, 8, 12)


class _RecordingMonthSource:
    """Month source returning a preset {date: Fare} and counting calls."""

    def __init__(self, month_fares: dict[dt.date, Fare]) -> None:
        self._fares = month_fares
        self.calls = 0

    def get_month(self, origin: str, destination: str, month: dt.date) -> dict[dt.date, Fare]:
        self.calls += 1
        return dict(self._fares)


def _month_fares() -> dict[dt.date, Fare]:
    return {
        _AUG10: Fare("LON", "LIS", _AUG10, 33.0, "EUR", "travelpayouts"),
        _AUG12: Fare("LON", "LIS", _AUG12, 32.0, "EUR", "travelpayouts"),
    }


def test_caching_month_warms_whole_month_on_one_miss() -> None:
    store = InMemoryFareCache()
    source = _RecordingMonthSource(_month_fares())
    provider = CachingMonthProvider(source, store)

    got = provider.get_fare("LON", "LIS", _AUG10)

    assert got is not None and got.price == 33.0
    assert got.source == "cached"  # re-stamped, like CachingLiveProvider
    assert source.calls == 1
    assert store.get("LON", "LIS", _AUG12) is not None  # the OTHER day was warmed too


def test_caching_month_second_day_same_month_is_a_cache_hit() -> None:
    source = _RecordingMonthSource(_month_fares())
    provider = CachingMonthProvider(source, InMemoryFareCache())

    provider.get_fare("LON", "LIS", _AUG10)
    provider.get_fare("LON", "LIS", _AUG12)  # same month, already warmed

    assert source.calls == 1  # one API call served both days


def test_caching_month_absent_day_returns_none_without_refetch() -> None:
    source = _RecordingMonthSource(_month_fares())
    provider = CachingMonthProvider(source, InMemoryFareCache())

    assert provider.get_fare("LON", "LIS", _AUG11) is None  # no price that day
    assert provider.get_fare("LON", "LIS", _AUG11) is None  # still none
    assert source.calls == 1  # guard stops re-fetching a known-absent day's month


def test_caching_month_serves_from_store_without_fetching() -> None:
    store = InMemoryFareCache()
    store.put(Fare("LON", "LIS", _AUG10, 20.0, "EUR", "cached"))
    source = _RecordingMonthSource(_month_fares())

    got = CachingMonthProvider(source, store).get_fare("LON", "LIS", _AUG10)

    assert got is not None and got.price == 20.0  # from the store
    assert source.calls == 0  # store hit, live never touched
