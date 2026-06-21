"""Thin orchestrator: build a memoized fare_lookup from a FareProvider, run an engine."""

import functools
from datetime import date

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.optimizer.bruteforce import search_bruteforce
from tripoptimizer.core.optimizer.heldkarp import search_heldkarp
from tripoptimizer.core.optimizer.models import TripRequest, TripResult


def optimize(
    request: TripRequest, provider: FareProvider, engine: str = "bruteforce"
) -> TripResult:
    # Per-request cache: the same (origin, dest, date) cell recurs across
    # permutations and offsets; memoizing collapses those to one provider call.
    @functools.lru_cache(maxsize=None)
    def fare_lookup(origin: str, destination: str, fly_date: date) -> tuple[float, str]:
        fare = provider.get_fare(origin, destination, fly_date)
        if fare is None:
            raise KeyError(f"no fare for {origin}->{destination} on {fly_date.isoformat()}")
        return (fare.price, fare.source)

    if engine == "heldkarp":
        return search_heldkarp(request, fare_lookup)
    return search_bruteforce(request, fare_lookup)
