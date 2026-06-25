"""Concurrent prefetch: warm the cache for every cell a trip could query."""

import datetime as dt
import time

from tripoptimizer.core.fares.models import Fare
from tripoptimizer.core.fares.on_demand import CachingLiveProvider, InMemoryFareCache
from tripoptimizer.core.optimizer.models import TripRequest
from tripoptimizer.core.optimizer.prefetch import cells_for_request, prefetch


def _trip(flex: int = 0) -> TripRequest:
    return TripRequest(
        cities=("BCN", "ROM"),
        days_per_city={"BCN": 2, "ROM": 3},
        origin_airport="LIS",
        return_airport="LIS",
        start_date=dt.date(2026, 7, 1),
        flex_days=flex,
    )


def test_cells_for_request_enumerates_both_orderings_at_flex_zero() -> None:
    assert cells_for_request(_trip(flex=0)) == {
        ("LIS", "BCN", dt.date(2026, 7, 1)),  # order BCN,ROM
        ("BCN", "ROM", dt.date(2026, 7, 3)),
        ("ROM", "LIS", dt.date(2026, 7, 6)),
        ("LIS", "ROM", dt.date(2026, 7, 1)),  # order ROM,BCN
        ("ROM", "BCN", dt.date(2026, 7, 4)),
        ("BCN", "LIS", dt.date(2026, 7, 6)),
    }


def test_cells_grow_with_the_flex_window() -> None:
    assert len(cells_for_request(_trip(flex=2))) > len(cells_for_request(_trip(flex=0)))


class _CountingLive:
    def __init__(self) -> None:
        self.calls: dict[tuple[str, str, dt.date], int] = {}

    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        key = (origin, destination, fly_date)
        self.calls[key] = self.calls.get(key, 0) + 1
        return Fare(origin, destination, fly_date, 50.0, "EUR", "travelpayouts")


def test_prefetch_warms_every_cell_exactly_once() -> None:
    live = _CountingLive()
    cache = InMemoryFareCache()
    trip = _trip(flex=1)

    prefetch(trip, CachingLiveProvider(live, cache))

    cells = cells_for_request(trip)
    assert all(cache.get(*cell) is not None for cell in cells)  # all warmed
    assert all(live.calls[cell] == 1 for cell in cells)  # no duplicate fetches


class _SlowLive:
    def get_fare(self, origin: str, destination: str, fly_date: dt.date) -> Fare | None:
        time.sleep(1.0)
        return Fare(origin, destination, fly_date, 50.0, "EUR", "travelpayouts")


def test_prefetch_returns_within_its_time_budget() -> None:
    # A slow source must not hold the request open for cells x latency; once the
    # budget is spent, unwarmed cells fall back to synthetic at optimize time.
    provider = CachingLiveProvider(_SlowLive(), InMemoryFareCache())
    started = time.monotonic()
    prefetch(_trip(flex=2), provider, max_workers=2, timeout_s=0.3)
    assert time.monotonic() - started < 3.0  # near the budget, not ~cells seconds
