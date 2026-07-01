"""Thin orchestrator: build a memoized fare_lookup from a FareProvider, run an engine.

With no synthetic fallback a cell can have no real fare; ``fare_lookup`` returns None and
the engine treats such an itinerary as infeasible. If no ordering is fully priceable the
run yields an IncompleteTrip naming the routes with no real fare on any queried date.
"""

import functools
from collections.abc import Callable
from datetime import date

from tripoptimizer.core.fares.base import FareProvider
from tripoptimizer.core.optimizer.bruteforce import search_bruteforce
from tripoptimizer.core.optimizer.heldkarp import search_heldkarp
from tripoptimizer.core.optimizer.models import IncompleteTrip, TripRequest, TripResult
from tripoptimizer.core.optimizer.prefetch import cells_for_request

FareLookup = Callable[[str, str, date], tuple[float, str] | None]


def optimize(
    request: TripRequest, provider: FareProvider, engine: str = "bruteforce"
) -> TripResult | IncompleteTrip:
    # Per-request cache: the same (origin, dest, date) cell recurs across
    # permutations and offsets; memoizing collapses those to one provider call.
    @functools.lru_cache(maxsize=None)
    def fare_lookup(origin: str, destination: str, fly_date: date) -> tuple[float, str] | None:
        fare = provider.get_fare(origin, destination, fly_date)
        return None if fare is None else (fare.price, fare.source)

    search = search_heldkarp if engine == "heldkarp" else search_bruteforce
    result = search(request, fare_lookup)
    if result is not None:
        return result
    return IncompleteTrip(_missing_routes(request, fare_lookup))


def _missing_routes(request: TripRequest, fare_lookup: FareLookup) -> tuple[tuple[str, str], ...]:
    """(origin, destination) pairs with no real fare on ANY queried date -- the
    structural gaps that block every ordering. Reuses the already-memoized fare_lookup,
    so this adds no extra provider calls."""
    dates_by_route: dict[tuple[str, str], list[date]] = {}
    for origin, destination, fly_date in cells_for_request(request):
        dates_by_route.setdefault((origin, destination), []).append(fly_date)
    missing = [
        route
        for route, dates in dates_by_route.items()
        if all(fare_lookup(route[0], route[1], d) is None for d in dates)
    ]
    return tuple(sorted(missing))
