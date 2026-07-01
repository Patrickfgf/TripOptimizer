"""Exhaustive search over city permutations x date offsets."""

from collections.abc import Callable
from datetime import date
from itertools import permutations

from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripRequest, TripResult
from tripoptimizer.core.optimizer.schedule import build_legs_dates

FareLookup = Callable[[str, str, date], tuple[float, str] | None]
MAX_ALTERNATIVES = 5


def _itinerary(
    order: tuple[str, ...],
    request: TripRequest,
    offset: int,
    fare_lookup: FareLookup,
) -> Itinerary | None:
    """Priced itinerary for one order+offset, or None if any leg has no real fare."""
    legs: list[Leg] = []
    total = 0.0
    for origin, destination, fly_date in build_legs_dates(order, request, offset):
        fare = fare_lookup(origin, destination, fly_date)
        if fare is None:
            return None  # infeasible: this ordering can't be fully priced from real data
        price, source = fare
        legs.append(Leg(origin, destination, fly_date, price, source))
        total += price
    return Itinerary(tuple(order), offset, tuple(legs), total)


def search_bruteforce(request: TripRequest, fare_lookup: FareLookup) -> TripResult | None:
    """Cheapest fully-real itinerary, or None if no order+offset is fully priceable."""
    offsets = range(-request.flex_days, request.flex_days + 1)
    candidates = [
        itinerary
        for order in permutations(request.cities)
        for offset in offsets
        if (itinerary := _itinerary(order, request, offset, fare_lookup)) is not None
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda it: it.total)
    return TripResult(best=candidates[0], alternatives=tuple(candidates[1 : 1 + MAX_ALTERNATIVES]))
