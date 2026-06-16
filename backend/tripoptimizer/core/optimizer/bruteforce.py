"""Exhaustive search over city permutations x date offsets."""

from collections.abc import Callable
from datetime import date
from itertools import permutations

from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripRequest, TripResult
from tripoptimizer.core.optimizer.schedule import build_legs_dates

FareLookup = Callable[[str, str, date], float]
MAX_ALTERNATIVES = 5


def _itinerary(
    order: tuple[str, ...],
    request: TripRequest,
    offset: int,
    fare_lookup: FareLookup,
) -> Itinerary:
    legs: list[Leg] = []
    total = 0.0
    for origin, destination, fly_date in build_legs_dates(order, request, offset):
        price = fare_lookup(origin, destination, fly_date)
        legs.append(Leg(origin, destination, fly_date, price))
        total += price
    return Itinerary(tuple(order), offset, tuple(legs), total)


def search_bruteforce(request: TripRequest, fare_lookup: FareLookup) -> TripResult:
    offsets = range(-request.flex_days, request.flex_days + 1)
    candidates = [
        _itinerary(order, request, offset, fare_lookup)
        for order in permutations(request.cities)
        for offset in offsets
    ]
    candidates.sort(key=lambda it: it.total)
    return TripResult(best=candidates[0], alternatives=tuple(candidates[1 : 1 + MAX_ALTERNATIVES]))
